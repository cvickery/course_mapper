#! /usr/local/bin/python3
""" Utilities used by the course_mapper.
"""

import psycopg
import re
import sys

from collections import defaultdict, namedtuple
from coursescache import courses_cache
from course_mapper_files import log_file, todo_file
from psycopg.rows import namedtuple_row

_parse_trees_cache = defaultdict(dict)

notyet_dict = {'not-yet': True}

number_names = ['none', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine',
                'ten', 'eleven', 'twelve']
number_ordinals = ['zeroth', 'first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh',
                   'eighth', 'ninth', 'tenth', 'eleventh', 'twelfth']

MogrifiedInfo = namedtuple('MogrifiedInfo', 'course_id_str course_str credits career with_clause')


# called_from()
# -------------------------------------------------------------------------------------------------
def called_from(depth=3, out_file=sys.stdout):
  """ Tell where the caller was called from (development aid)
  """
  if depth < 0:
    depth = 999

  caller_frames = extract_stack()

  for index in range(-2 - depth, -1):
    try:
      function_name = f'{caller_frames[index].name}()'
      file_name = caller_frames[index].filename
      file_name = file_name[file_name.rindex('/') + 1:]
      print(f'Frame: {function_name:20} at {file_name} '
            f'line {caller_frames[index].lineno}', file=out_file)
    except IndexError:
      # Dont kvetch if stack isn’t deep enough
      pass


# format_group_description()
# -------------------------------------------------------------------------------------------------
def format_group_description(num_groups: int, num_required: int):
  """ Return an English string to replace the label (requirement_name) for group requirements.
  """
  assert isinstance(num_groups, int) and isinstance(num_required, int), 'Precondition failed'

  suffix = '' if num_required == 1 else 's'
  if num_required < len(number_names):
    num_required_str = number_names[num_required].lower()
  else:
    num_required_str = f'{num_required:,}'

  s = '' if num_groups == 1 else 's'

  if num_groups < len(number_names):
    num_groups_str = number_names[num_groups].lower()
  else:
    num_groups_str = f'{num_groups:,}'

  if num_required == num_groups:
    if num_required == 1:
      prefix = 'The'
    elif num_required == 2:
      prefix = 'Both of the'
    else:
      prefix = 'All of the'
  elif (num_required == 1) and (num_groups == 2):
    prefix = 'Either of the'
  else:
    prefix = f'Any {num_required_str} of the'
  return f'{prefix} following {num_groups_str} group{s}'


# get_parse_tree()
# -------------------------------------------------------------------------------------------------
def get_parse_tree(dap_req_block_key: tuple) -> dict:
  """ Look up the parse tree for a dap_req_block.
      Cache it, and return it.
  """
  if dap_req_block_key not in _parse_trees_cache.keys():
    with psycopg.connect('dbname=cuny_curriculum') as conn:
      with conn.cursor(row_factory=namedtuple_row) as cursor:
        cursor.execute("""
        select period_start, period_stop, parse_tree
          from requirement_blocks
         where institution ~* %s
           and requirement_id = %s
        """, dap_req_block_key)
        assert cursor.rowcount == 1
        parse_tree = cursor.fetchone().parse_tree
        if parse_tree is None:
          institution, requirement_id = dap_req_block_key
          parse_tree = parse_block(institution, requirement_id, row.period_start, row.period_stop)
          print(f'{institution} {requirement_id} Reference to un-parsed block', file=log_file)
    _parse_trees_cache[dap_req_block_key] = parse_tree

  return _parse_trees_cache[dap_req_block_key]


# get_restrictions()
# -------------------------------------------------------------------------------------------------
def get_restrictions(node: dict) -> dict:
  """ Return qualifiers that might affect transferability.
  """
  assert isinstance(node, dict)

  return_dict = dict()
  # The maxtransfer restriction puts a limit on the number of classes or credits that can be
  # transferred, possibly with a list of "types" for which the limit applies. I think the type names
  # have to come from a dgw table somewhere.
  try:
    transfer_dict = node['maxtransfer']
    return_dict['maxtransfer'] = transfer_dict
  except KeyError:
    pass

  # The mingrade restriction puts a limit on the minimum required grade for all courses in a course
  # list. It’s a float (like a GPA) in Scribe, but is replaced with a letter grade here.
  mingrade_dict = {}
  try:
    mingrade_dict = node['mingrade']
    number = float(mingrade_dict['number'])
    grade_str = letter_grade(number)
    return_dict['mingrade'] = grade_str
  except KeyError:
    pass

  return return_dict


# letter_grade()
# -------------------------------------------------------------------------------------------------
def letter_grade(grade_point: float) -> str:
  """ Convert a passing grade_point value to a passing letter grade.
      Treat anything less than 1.0 as "Any" passing grade, and anything above 4.3 as "A+"
        GPA Letter
        4.3    A+
        4.0    A
        3.7    A-
        3.3    B+
        3.0    B
        2.7    B-
        2.3    C+
        2.0    C
        1.7    C-
        1.3    D+
        1.0    D
        0.7    D- => "Any"
  """
  if grade_point < 1.0:
    return 'Any'
  else:
    letter_index, suffix_index = divmod((10 * grade_point) - 7, 10)
  letter = ['D', 'C', 'B', 'A'][min(int(letter_index), 3)]
  suffix = ['-', '', '+'][min(int(suffix_index / 3), 2)]
  return letter + suffix


# Header Constructs
# =================================================================================================

# header_classcredit()
# -------------------------------------------------------------------------------------------------
def header_classcredit(institution: str, requirement_id: str,
                       value: dict, do_proxyadvice: bool) -> dict:
  """
      This is the “total credits and/or total classes” part of the header, which we are calling
      “requirement size”. Conditionals my cause multiple instances to be specified, which is why
      this value is maintained as a list, which may also contain interspersed conditionals.
  """
  return_dict = dict()

  # There's always a label key, but the value may be empty
  if label_str := value['label']:
    return_dict['label'] = label_str

  try:
    # There might or might-not be proxy-advice
    proxy_advice = value['proxy_advice']
    if do_proxyadvice:
      return_dict['proxy_advice'] = value['proxy_advice']
  except KeyError:
    # No proxy-advice (normal))
    pass

  return_dict['is_pseudo'] = value['is_pseudo']

  min_classes = None if value['min_classes'] is None else int(value['min_classes'])
  min_credits = None if value['min_credits'] is None else float(value['min_credits'])
  max_classes = None if value['max_classes'] is None else int(value['max_classes'])
  max_credits = None if value['max_credits'] is None else float(value['max_credits'])

  classes_part = ''
  if min_classes or max_classes:
    assert min_classes and max_classes, f'{min_classes=} {max_classes=}'
    if min_classes == max_classes:
      classes_part = (f'{max_classes} classes')
    else:
      classes_part = (f'{min_classes}-{max_classes} classes')

  credits_part = ''
  if min_credits or max_credits:
    if min_credits == max_credits:
      credits_part = (f'{max_credits:.1f} credits')
    else:
      credits_part = (f'{min_credits:.1f}-{max_credits:.1f} credits')

  if classes_part and credits_part:
    conjunction = value['conjunction']
    assert conjunction is not None, f'{classes_part=} {credits_part=}'
    return_dict['size'] = f'{classes_part} {conjunction} {credits_part}'
  elif classes_part or credits_part:
    # One of them is blank
    return_dict['size'] = classes_part + credits_part
  else:
    exit('Malformed header_class_credit')

  return return_dict


# header_maxtransfer()
# -------------------------------------------------------------------------------------------------
def header_maxtransfer(institution: str, requirement_id: str, value: dict) -> dict:
  """
  """
  mt_dict = {'label': value['label']}

  number = float(value['maxtransfer']['number'])
  class_or_credit = value['maxtransfer']['class_or_credit']
  if class_or_credit == 'credit':
    mt_dict['limit'] = f'{number:3.1f} credits'
  else:
    suffix = '' if int(number) == 1 else 'es'
    mt_dict['limit'] = f'{int(number):3} class{suffix}'
  try:
    mt_dict['transfer_types'] = value['transfer_types']
  except KeyError:
    pass

  return mt_dict


# header_minres()
# -------------------------------------------------------------------------------------------------
def header_minres(institution: str, requirement_id: str, value: dict) -> dict:
  """ Return a dict with the number of classes or credits (it's always credits, in practice) plus
      the label if there is one.
  """
  min_classes = value['minres']['min_classes']
  min_credits = value['minres']['min_credits']
  # There must be a better way to do an xor check ...
  match (min_classes, min_credits):
    case [classes, None]:
      minres_str = f'{int(classes)} classes'
    case [None, credits]:
      minres_str = f'{float(credits):.1f} credits'
    case _:
      exit(f'{institution} {requirement_id} Invalid minres {value}')

  label_str = value['label']

  return {'minres': minres_str, 'label': label_str}


# header_mingpa()
# -------------------------------------------------------------------------------------------------
def header_mingpa(institution: str, requirement_id: str, value: dict) -> dict:
  """
  """
  mingpa_dict = value['mingpa']
  mingpa_dict['label'] = value['label']

  return mingpa_dict


# header_mingrade()
# -------------------------------------------------------------------------------------------------
def header_mingrade(institution: str, requirement_id: str, value: dict) -> dict:
  """
  """
  mingrade_dict = value['mingrade']
  mingrade_dict['letter_grade'] = letter_grade(float(value['mingrade']['number']))
  mingrade_dict['label'] = value['label']

  return mingrade_dict


# header_maxclass()
# -------------------------------------------------------------------------------------------------
def header_maxclass(institution: str, requirement_id: str, value: dict) -> dict:
  """
  """

  try:
    for cruft_key in ['institution', 'requirement_id']:
      del(value['maxclass']['course_list'][cruft_key])
  except KeyError:
    # The same block might have been mapped in a different context already
    pass

  number = int(value['maxclass']['number'])
  course_list = value['maxclass']['course_list']
  course_list['courses'] = [{'course_id': course_info.course_id_str,
                             'course': course_info.course_str,
                             'with': course_info.with_clause}
                            for course_info in mogrify_course_list(institution,
                                                                   requirement_id,
                                                                   course_list)]
  maxclass_dict = {'label': value['label'],
                   'number': number,
                   'courses': course_list
                   }

  return maxclass_dict


# header_maxcredit()
# -------------------------------------------------------------------------------------------------
def header_maxcredit(institution: str, requirement_id: str, value: dict) -> dict:
  """
  """
  try:
    for cruft_key in ['institution', 'requirement_id']:
      del(value['maxcredit']['course_list'][cruft_key])
  except KeyError:
    pass

  number = float(value['maxcredit']['number'])
  course_list = value['maxcredit']['course_list']
  course_list['courses'] = [{'course_id': course_info.course_id_str,
                             'course': course_info.course_str,
                             'with': course_info.with_clause}
                            for course_info in mogrify_course_list(institution,
                                                                   requirement_id,
                                                                   course_list)]

  maxcredit_dict = {'label': value['label'],
                    'number': number,
                    'courses': course_list
                    }

  return maxcredit_dict


# header_maxpassfail()
# -------------------------------------------------------------------------------------------------
def header_maxpassfail(institution: str, requirement_id: str, value: dict) -> dict:
  """
  """
  maxpassfail_dict = value['maxpassfail']
  maxpassfail_dict['label'] = value['label']

  return maxpassfail_dict


# header_maxperdisc()
# -------------------------------------------------------------------------------------------------
def header_maxperdisc(institution: str, requirement_id: str, value: dict) -> dict:
  """
  """
  maxperdisc_dict = value['maxperdisc']
  maxperdisc_dict['label'] = value['label']

  return maxperdisc_dict


# header_minclass()
# -------------------------------------------------------------------------------------------------
def header_minclass(institution: str, requirement_id: str, value: dict) -> dict:
  """
  """
  minclass_dict = value['minclass']
  minclass_dict['label'] = value['label']

  return minclass_dict


# header_mincredit()
# -------------------------------------------------------------------------------------------------
def header_mincredit(institution: str, requirement_id: str, value: dict) -> dict:
  """
  """
  mincredit_dict = value['mincredit']
  mincredit_dict['label'] = value['label']

  return mincredit_dict


# header_minperdisc()
# -------------------------------------------------------------------------------------------------
def header_minperdisc(institution: str, requirement_id: str, value: dict) -> dict:
  """
  """
  minperdisc_dict = value['minperdisc']
  minperdisc_dict['label'] = value['label']

  return minperdisc_dict


# header_proxyadvice()
# -------------------------------------------------------------------------------------------------
def header_proxyadvice(institution: str, requirement_id: str, value: dict) -> dict:
  """
  """
  print(f'{institution} {requirement_id} header_proxyadvice', file=todo_file)
  return notyet_dict


# mogrify_context_list()
# -------------------------------------------------------------------------------------------------
def mogrify_context_list(context_list: list) -> list:
  """
      Given a context list, extract a list of strings that summarizes the info from each dict in the
      list
  """
  return_list = []
  for element in context_list:
    for key, value in element.items():
      match key:

        case 'block_info':
          return_list.append(f'{value["requirement_id"]} {value["block_type"]} '
                             f'{value["block_value"]}')

        case 'if_true':
          return_list.append(f'TRUE: {value}')

        case 'if_false':
          return_list.append(f'FALSE: {value}')

        case 'requirement_name':
          return_list.append(value)

        case 'num_groups' | 'num_required' | 'remark':
          pass

        case _:
          exit(element)

  return return_list


# mogrify_course_list()
# -------------------------------------------------------------------------------------------------
def mogrify_course_list(institution: str, requirement_id: str, course_dict: dict) -> list:
  """
      This gets called from traverse_header (max_classes, max_credits), and map_courses (via various
      body rules) to turn a scribed course_list into information needed for populating the programs
      table (header info) or mapping table (body rules).

      First flatten the dict of scribed courses to get rid of the areas structure.
        Log cases where there is more than one area
      Create a set of courses (eliminates duplicates)
      Use courses_cache() to look up catalog_information for each course in the courses set.
      The courses_cache handles wildcard expansion.

      Use courses_cache to look up catalog information for all matchig courses for each course in
      the exclude list.
      Remove excluded courses from the courses_set.
      Distribute certain with_clauses onto courses; ignore others
      return the list of CourseInfo items.

  The course_dict has three course lists to be managed: scribed, include, and exclude. (Terminology
  note: the Scribe language uses “except” for what I’m calling “exclude.”) The include and exclude
  lists may be empty. Each list consists of 3-tuples: {discipline, catalog_number, with-clause}.
  Disciplines and catalog numbers can contain wildcards (@), and catalog_numbers can specify ranges
  (:). With-clauses are optional (i.e., can be None).

  We ignore include lists here, but log them for possible future action.

  With-clauses in the scribed list are distributed across all courses in the list after wildcard and
  range expansion.

  With-clauses might or might not be significant. Based on samples examined (see below), two cases
  are currently logged but otherwise ignored: references to DWTerm (because they seem to refer to
  special policies during the COVID pandemic) and references to course attributes. Attributes might
  actually specify requirements, such as writing intensive courses, although the cases seen so far
  only apply to some hidden requirements referring to Pathways requirements. Note, however, that the
  use of ATTRIBUTE=FCER, etc. in the examples found don't make sense: FCER is a requirement
  designation, not a course attribute.

  Sample cases encountered across CUNY:

    CSI01 RA001460 Exclude course based on DWTerm (ignored)
      MaxCredits 0 in @ @ (With DWPassfail=Y)
        Except @ @ (With DWTerm = 1202) # allow p/f classes in spring 2020 to apply

    CTY01 RA000718 Exclude course
      MaxCredits 6 in @ @ (With DWTransfer=Y)
      EXCEPT PHYS 20300, 20400, 20700, 20800 ## Updated as of 1/13/20

    HTR01 RA002566 Exclude course
      MaxCredits 30 in ARTCR 1@, 2@, 3@, 4@ Except ARTCR 10100

    HTR01 RA002617 Exclude course
      MaxCredits 3 in ECO 1@ Except ECO 10000

    NYT01 RA000727
      BeginSub
            2 Classes in ARTH 1@, AFR 1301, 1304
        Label 1.1 "ARTH 1100-SERIES OR AFR 1301, 1304";
            1 Class in ARTH 3311,
              {HIDE @ (WITH ATTRIBUTE=FCER and DWTransfer = Y),}
              {HIDE @ (WITH ATTRIBUTE=FCEC and DWTransfer = Y),}
              {HIDE @ (WITH ATTRIBUTE=FCED and DWTransfer = Y)}
       RuleTag Category=FCCE1
       Label 1.2 "Creative Expression";
      EndSub
       Label 1.0 "Required Gen. Ed.";
         Remark "Transferred students are allowed to fulfill the Creative Expression area with any
         approved Creative Expression from their prior school.";

  """
  # There has to be a course_dict to mogrify
  assert course_dict, 'Empty course_dict in mogrify_course_dict'

  # Log non-empty include lists
  if course_dict['include_courses']:
    print(f'{institution} {requirement_id} Non-empty include_courses (ignored)', file=log_file)

  # Get the scribed list, which is divided into areas even if there are nont, and flatten it.
  course_list = course_dict['scribed_courses']
  # Course tuples are (0: discipline, 1: catalog_number, 2: with_clause)
  course_tuples = [tuple(course) for area in course_list for course in area]
  # Get rid of redundant scribes
  course_tuples_set = set([course_tuple for course_tuple in course_tuples])

  # Create a set of active courses and a dict of corresponding with-clauses
  course_info_set = set()
  with_clauses = dict()
  for course_tuple in course_tuples_set:
    course_infos = courses_cache(institution, course_tuple[0], course_tuple[1])
    for course_info in course_infos:
      if course_tuple[2]:
        with_clause = course_tuple[2].lower()
        if 'dwterm' in with_clause or 'attribute' in with_clause:
          continue
        with_key = (course_info.course_id, course_info.offer_nbr)
        if with_key in with_clauses.keys() and with_clauses[with_key] != course_tuple[2].lower():
          print(f'{institution} {requirement_id} Mogrify: multiple with-clauses. '
                f'{with_clauses[with_key]} != {course_tuple[2].lower()}',
                file=debug_file)
        with_clauses[with_key] = course_tuple[2].lower()
      course_info_set.add(course_info)

  # Create set of exclude courses (there is no areas structure in exclude lists)
  exclude_list = course_dict['except_courses']
  exclude_tuples_set = set([tuple(course) for course in exclude_list])
  exclude_info_set = set()
  for exclude_tuple in exclude_tuples_set:
    course_infos = courses_cache(institution, exclude_tuple[0], exclude_tuple[1])
    for course_info in course_infos:
      exclude_info_set.add(course_info)

  if len(exclude_info_set):
    print(f'{institution} {requirement_id} Non-empty exclude list', file=log_file)

  # Log any with-clauses in the exclude list to determine whether they need to be dealt with.
  for discipline, catalog_number, with_clause in exclude_list:
    if with_clause:
      # Ignore cases where the with clause references DWTerm: they look like COVID special cases,
      # and even if they are not, they can’t be “program requirements”
      if 'dwterm' in with_clause.lower():
        print(f'{institution} {requirement_id} Exclude course based on DWTerm (ignored)',
              file=log_file)
      else:
        # Log and skip remaining cases that have with-expressions
        """ If there is a grade or transfer restriction, one might be able to invert it and simply
            add it to the with clause of all the scribed_courses. But for now, we're just finding
            out whether it is a real issue or not.
        """
        print(f'{institution} {requirement_id} mogrify_course_list(): exclude with {with_clause}',
              file=todo_file)

  # Remove excluded courses from the courses
  course_info_set -= exclude_info_set

  return_list = []
  for course in course_info_set:
    with_key = (course_info.course_id, course_info.offer_nbr)
    with_clause = with_clauses[with_key] if with_key in with_clauses.keys() else ''
    # MogrifiedInfo = namedtuple('MogrifiedInfo', 'course_id_str course_str career with_clause')
    mogrified_info = MogrifiedInfo._make([f'{course.course_id:06}:{course.offer_nbr}',
                                          f'{course.discipline} {course.catalog_number}: '
                                          f'{course.course_title}',
                                          course.credits,
                                          course.career,
                                          with_clause])
    return_list.append(mogrified_info)
  return return_list


# mogrify_expression()
# -------------------------------------------------------------------------------------------------
def mogrify_expression(expression: str, de_morgan: bool = False) -> str:
  """ If the expression specifies a set of major or concentration conditions, return an
      English sentence describing those conditions. Otherwise, return the empty string.

      The three logical operators (and, or, not) and parens have to be handled.
      The only relational operators that will occur are = and <>

      If de_morgan, invert the logic by de Morgan's theorem. (Used in an 'else' context)
  """

  sentence = ''

  # Is there anything to do?
  if re.search('major |conc ', expression, flags=re.I):
    # Replace logical and relational operators with 1-character symbols.
    # relop = is already one char; <> is awkward: I chose to use ^
    working_expression = (expression.strip()
                                    .replace(' AND ', ' & ')
                                    .replace(' OR ', ' | ')
                                    .replace(' NOT ', ' ! ')
                                    .replace(' <> ', ' ^ '))
    tokens = working_expression.split()
    for token in tokens:
      match token:
        case 'MAJOR':
          sentence += 'Major '
        case 'MINOR':
          sentence += 'Minor '
        case 'CONC':
          sentence += 'Concentration '
        case '&':
          sentence += 'or ' if de_morgan else 'and '
        case '|':
          sentence += 'and ' if de_morgan else 'or '
        case '!':
          # NOT is not expected here
          sentence += '-not- '
        case '=':
          sentence += 'is not ' if de_morgan else 'is '
        case '^':
          sentence += 'is ' if de_morgan else'is not '
        case _:
          sentence += f'{token} '

  return sentence.strip()


if __name__ == '__main__':
  while expression := input('expression? '):
    mogrify_expression(expression)
