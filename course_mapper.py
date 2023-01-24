#! /usr/local/bin/python3
""" List program requirements and courses that satisfy them.
"""

import csv
import datetime
import os
import json
import psycopg
import re
import sys
import traceback

from activeplans import active_plans
from argparse import ArgumentParser
from catalogyears import catalog_years
from collections import namedtuple, defaultdict
from copy import copy, deepcopy
from coursescache import courses_cache
from dgw_parser import parse_block
from psycopg.rows import namedtuple_row, dict_row
from quarantine_manager import QuarantineManager
from recordclass import recordclass
from traceback import extract_stack
from typing import Any

from course_mapper_files import anomaly_file, blocks_file, fail_file, log_file, no_courses_file, \
    subplans_file, todo_file, programs_file, requirements_file, mapping_file, label_file

from course_mapper_utils import format_group_description, get_parse_tree, get_restrictions, \
    header_classcredit, header_maxtransfer, header_minres, header_mingpa, header_mingrade, \
    header_maxclass, header_maxcredit, header_maxpassfail, header_maxperdisc, header_minclass, \
    header_mincredit, header_minperdisc, header_proxyadvice, letter_grade, mogrify_context_list, \
    mogrify_course_list, number_names, number_ordinals


programs_writer = csv.writer(programs_file)
requirements_writer = csv.writer(requirements_file)
map_writer = csv.writer(mapping_file)

generated_date = str(datetime.date.today())

requirement_key = 0

quarantine_manager = QuarantineManager()

program_blocks_list = []
reference_counts = defaultdict(int)
reference_callers = defaultdict(list)
Reference = namedtuple('Reference', 'name lineno')


# =================================================================================================

# header_conditional()
# -------------------------------------------------------------------------------------------------
def header_conditional(institution: str, requirement_id: str,
                       return_dict: dict, conditional_dict: dict):
  """
      Update the return_dict with conditional info determined by traversing the conditional_dict
      recursively.
  """

  # The header columns that might be updated:
  column_lists = ['total_credits_list', 'maxtransfer_list',
                  'minres_list', 'mingrade_list', 'mingpa_list']

  # The lists in the Other column that might be updated:
  other_lists = ['total_credits_list', 'maxcredit_list', 'maxtransfer_list',
                 'minclass_list', 'mincredit_list', 'minres_list', 'mingrade_list', 'mingpa_list']

  condition_str = conditional_dict['conditional']['condition_str']
  tagged_true_lists = []
  tagged_false_lists = []

  # Possible values for which_leg
  true_leg = True
  false_leg = False

  def tag(which_list, which_leg=true_leg):
    """ Manage the first is_true and, possibly, is_false for each list.
    """
    if args.concise_conditionals:
      which_dict = {'if': condition_str} if which_leg else {'else': ''}
    else:
      which_dict = {'if_true': condition_str} if which_leg else {'if_false': condition_str}

    if which_leg == true_leg and which_list not in tagged_true_lists:
      tagged_true_lists.append(which_list)
      if which_list in column_lists:
        return_dict[which_list].append(which_dict)
      elif which_list in other_lists:
        return_dict['other'][which_list].append(which_dict)
      else:
        exit(f'{which_list} is not in column_lists or other_lists')

    if which_leg == false_leg and which_list not in tagged_false_lists:
      tagged_false_lists.append(which_list)
      if which_list in column_lists:
        return_dict[which_list].append(which_dict)
      elif which_list in other_lists:
        return_dict['other'][which_list].append(which_dict)
      else:
        exit(f'{which_list} is not in column_lists or other_lists')

  # True leg handlers
  # -----------------
  if true_dict := conditional_dict['conditional']['if_true']:
    for requirement in true_dict:
      for key, value in requirement.items():
        match key:

          case 'conditional':
            print(f'{institution} {requirement_id} Header conditional true {key}', file=log_file)
            header_conditional(institution, requirement_id, return_dict, requirement)

          case 'header_class_credit':
            print(f'{institution} {requirement_id} Header conditional true {key}', file=log_file)
            tag('total_credits_list', true_leg)
            return_dict['total_credits_list'].append(header_classcredit(institution, requirement_id,
                                                                        value, do_proxyadvice))

          case 'header_maxtransfer':
            print(f'{institution} {requirement_id} Header conditional true {key}', file=log_file)
            tag('maxtransfer_list', true_leg)
            return_dict['maxtransfer_list'].append(header_maxtransfer(institution, requirement_id,
                                                                      value))

          case 'header_minres':
            print(f'{institution} {requirement_id} Header conditional true {key}', file=log_file)
            tag('minres_list', true_leg)
            return_dict['minres_list'].append(header_minres(institution, requirement_id, value))

          case 'header_mingpa':
            print(f'{institution} {requirement_id} Header conditional true {key}', file=log_file)
            tag('mingpa_list', true_leg)
            return_dict['mingpa_list'].append(header_mingpa(institution, requirement_id, value))

          case 'header_mingrade':
            print(f'{institution} {requirement_id} Header conditional true {key}', file=log_file)
            tag('mingrade_list', true_leg)
            return_dict['mingrade_list'].append(header_mingrade(institution, requirement_id, value))

          case 'header_maxclass':
            print(f'{institution} {requirement_id} Header conditional true {key}', file=log_file)
            tag('maxclass_list', true_leg)
            return_dict['other']['maxclass_list'].append(header_maxclass(institution,
                                                                         requirement_id, value))

          case 'header_maxcredit':
            print(f'{institution} {requirement_id} Header conditional true {key}', file=log_file)
            tag('maxcredit_list', true_leg)
            return_dict['other']['maxcredit_list'].append(header_maxcredit(institution,
                                                                           requirement_id, value))

          case 'header_maxpassfail':
            print(f'{institution} {requirement_id} Header conditional true {key}', file=log_file)
            tag('maxpassfail_list', true_leg)
            return_dict['other']['maxpassfail_list'].append(header_maxpassfail(institution,
                                                                               requirement_id,
                                                                               value))

          case 'header_maxperdisc':
            print(f'{institution} {requirement_id} Header conditional true {key}', file=log_file)
            tag('maxperdisc_list', true_leg)
            return_dict['other']['maxperdisc_list'].append(header_maxperdisc(institution,
                                                                             requirement_id, value))

          case 'header_minclass':
            print(f'{institution} {requirement_id} Header conditional true {key}', file=log_file)
            tag('minclass_list', true_leg)
            return_dict['other']['minclass_list'].append(header_minclass(institution,
                                                                         requirement_id, value))

          case 'header_mincredit':
            print(f'{institution} {requirement_id} Header conditional true {key}', file=log_file)
            tag('mincredit_list', true_leg)
            return_dict['other']['mincredit_list'].append(header_mincredit(institution,
                                                                           requirement_id, value))

          case 'header_minperdisc':
            print(f'{institution} {requirement_id} Header conditional true {key}', file=log_file)
            tag('minperdisc_list', true_leg)
            return_dict['other']['minperdisc_list'].append(header_minperdisc(institution,
                                                                             requirement_id, value))

          case 'header_share':
            # Ignore
            pass

          case 'proxyadvice':
            if do_proxy_advice:
              print(f'{institution} {requirement_id} Header conditional true {key}', file=log_file)
              tag('proxyadvice_list', true_leg)
              return_dict['other']['proxyadvice_list'].append(value)
            else:
              print(f'{institution} {requirement_id} Header conditional true {key} (ignored)',
                    file=log_file)
              pass

          case _:
            print(f'{institution} {requirement_id} Conditional-true {key} not implemented (yet)',
                  file=todo_file)

  # False (else) leg handlers
  # -------------------------
  try:
    false_dict = conditional_dict['conditional']['if_false']
    for requirement in false_dict:
      for key, value in requirement.items():
        match key:

          case 'conditional':
            print(f'{institution} {requirement_id} Header conditional false {key}', file=log_file)
            header_conditional(institution, requirement_id, return_dict, requirement)

          case 'header_class_credit':
            print(f'{institution} {requirement_id} Header conditional false {key}', file=log_file)
            tag('total_credits_list', false_leg)
            return_dict['total_credits_list'].append(header_classcredit(institution,
                                                                        requirement_id,
                                                                        value, do_proxyadvice))

          case 'header_maxtransfer':
            print(f'{institution} {requirement_id} Header conditional false {key}', file=log_file)
            tag('maxtransfer_list', false_leg)
            return_dict['maxtransfer_list'].append(header_maxtransfer(institution, requirement_id,
                                                                      value))

          case 'header_minres':
            print(f'{institution} {requirement_id} Header conditional false {key}', file=log_file)
            tag('minres_list', false_leg)
            return_dict['minres_list'].append(header_minres(institution, requirement_id, value))

          case 'header_mingpa':
            print(f'{institution} {requirement_id} Header conditional false {key}', file=log_file)
            tag('mingpa_list', false_leg)
            return_dict['mingpa_list'].append(header_mingpa(institution, requirement_id, value))

          case 'header_mingrade':
            print(f'{institution} {requirement_id} Header conditional false {key}', file=log_file)
            tag('mingrade_list', false_leg)
            return_dict['mingrade_list'].append(header_mingrade(institution, requirement_id,
                                                                value))

          case 'header_maxclass':
            print(f'{institution} {requirement_id} Header conditional false {key}', file=log_file)
            tag('maxclass_list', false_leg)
            return_dict['other']['maxclass_list'].append(header_maxclass(institution,
                                                                         requirement_id, value))

          case 'header_maxcredit':
            print(f'{institution} {requirement_id} Header conditional false {key}', file=log_file)
            tag('maxcredit_list', false_leg)
            return_dict['other']['maxcredit_list'].append(header_maxcredit(institution,
                                                                           requirement_id, value))

          case 'header_maxpassfail':
            print(f'{institution} {requirement_id} Header conditional false {key}', file=log_file)
            tag('maxpassfail_list', false_leg)
            return_dict['other']['maxpassfail_list'].append(header_maxpassfail(institution,
                                                                               requirement_id,
                                                                               value))

          case 'header_maxperdisc':
            print(f'{institution} {requirement_id} Header conditional false {key}', file=log_file)
            tag('maxperdisc_list', false_leg)
            return_dict['other']['maxperdisc_list'].append(header_maxperdisc(institution,
                                                                             requirement_id,
                                                                             value))

          case 'header_minclass':
            print(f'{institution} {requirement_id} Header conditional false {key}', file=log_file)
            tag('minclass_list', false_leg)
            return_dict['other']['minclass_list'].append(header_minclass(institution,
                                                                         requirement_id, value))

          case 'header_mincredit':
            print(f'{institution} {requirement_id} Header conditional false {key}', file=log_file)
            tag('mincredit_list', false_leg)
            return_dict['other']['mincredit_list'].append(header_mincredit(institution,
                                                                           requirement_id,
                                                                           value))

          case 'header_minperdisc':
            print(f'{institution} {requirement_id} Header conditional false {key}', file=log_file)
            tag('minperdisc_list', false_leg)
            return_dict['other']['minperdisc_list'].append(header_minperdisc(institution,
                                                                             requirement_id,
                                                                             value))

          case 'header_share':
            print(f'{institution} {requirement_id} Header conditional false {key}', file=log_file)
            # Ignore
            pass

          case 'proxyadvice':
            if do_proxy_advice:
              print(f'{institution} {requirement_id} Header conditional true {key}',
                    file=log_file)
              tag('proxyadvice_list', false_leg)
              return_dict['other']['proxyadvice_list'].append(value)
            else:
              print(f'{institution} {requirement_id} Header conditional true {key} (ignored)',
                    file=log_file)
              pass

          case _:
            print(f'{institution} {requirement_id} Conditional-false {key} not implemented (yet)',
                  file=todo_file)
  except KeyError:
    # False part is optional
    pass

  # Mark the end of this conditional. The condition_str is for verification, not logically needed.
  if args.concise_conditionals:
    condition_str = ''
  for tagged_list in tagged_true_lists:
    if tagged_list in column_lists:
      return_dict[tagged_list].append({'endif': condition_str})
    else:
      return_dict['other'][tagged_list].append({'endif': condition_str})


# body_conditional()
# -------------------------------------------------------------------------------------------------
def body_conditional(institution: str, requirement_id: str,
                     context_list: list, conditional_dict: dict):
  """
      Update the return_dict with conditional info determined by traversing the conditional_dict
      recursively.
  """

  condition_str = conditional_dict['condition_str']
  begin_true = {'if': condition_str} if args.concise_conditionals else {'if_true': condition_str}
  begin_false = {'else': ''} if args.concise_conditionals else {'if_false': condition_str}

  if true_dict := conditional_dict['if_true']:
    context_list.append(begin_true)
    traverse_body(true_dict, context_list)
    context_list.pop()

  try:
   false_dict = conditional_dict['if_false']
   context_list.append(begin_false)
   traverse_body(false_dict, context_list)
   context_list.pop()
  except KeyError as err:
    # false leg is optional
    pass


# map_courses()
# -------------------------------------------------------------------------------------------------
def map_courses(institution: str, requirement_ids: str, block_title: str, context_list: list,
                requirement_dict: dict):
  """ Write courses and their With clauses to the map file.
      Object returned by courses_cache():
        CourseTuple = namedtuple('CourseTuple', 'course_id offer_nbr title credits career')

      Each program requirement has a unique key based on institution, requirement_id, block_title,
      and context list.

Programs: Handled by process_block()
Institution, Requirement ID, Type, Code, Total, Max Transfer, Min Residency, Min Grade, Min GPA

Requirements: Handled here
Institution, Requirement ID, Requirement Key, Name, Context, Grade Restriction, Transfer Restriction

Course Mappings: Handled here
Requirement Key, Course ID, Career, Course, With

  """

  # The requirement_key is used to join the requirements and the courses that map to them.
  global requirement_key
  requirement_key += 1

  # Copy the requirement_dict in case a local version has to be constructed
  requirement_info = deepcopy(requirement_dict)
  try:
    course_list = requirement_info['course_list']
  except KeyError:
    # Sometimes the course_list _is_ the requirement. In these cases, all scribed courses are
    # (assumed to be) required. So create a requirement_info dict with a set of values to reflect
    # this.
    course_list = requirement_dict
    num_scribed = sum([len(area) for area in course_list['scribed_courses']])
    requirement_info = {'label': 'Unnamed Requirement',
                        'conjunction': None,
                        'course_list': requirement_dict,
                        'max_classes': num_scribed,
                        'max_credits': None,
                        'min_classes': num_scribed,
                        'min_credits': None,
                        'allow_classes': None,
                        'allow_credits': None}
    try:
      # Ignore context_path provided by dgw_parser, if it is present. (It just makes the course list
      # harder to read)
      del course_list['context_path']
    except KeyError:
      pass

  requirement_id_list = requirement_ids.split(':')
  requirement_id = requirement_id_list[0]
  other_requirement_ids = ':'.join(requirement_id_list[1:])

  # Put the course_list into "canonical form"
  canonical_course_list = mogrify_course_list(institution, requirement_id, course_list)
  requirement_info['num_courses'] = len(canonical_course_list)
  if requirement_info['num_courses'] == 0:
    print(institution, requirement_id, file=no_courses_file)
  else:
    # Map all the courses for the requirement ...
    for course_info in canonical_course_list:
      row = [requirement_key,
             course_info.course_id_str,
             course_info.career,
             course_info.course_str,
             json.dumps(course_info.with_clause, ensure_ascii=False),
             generated_date]
      map_writer.writerow(row)

    # ... and add the requirement to the requirements table
    requirement_name = requirement_info['label']
    """ Check requirement name for <COURSETITLE> & <COURSECREDITS> """
    # Title and credits come from first course listed if there are multiple courses
    course_info = canonical_course_list[0]
    if '<COURSETITLE>' in requirement_name.upper():
      # course_info.course_str is "discipline catalog_number: title" (title might contain colons)
      _, course_title = course_info.course_str.split(':', 1)
      course_title = course_title.strip()
      requirement_name = re.sub(r'<coursetitle>', course_title, requirement_name,
                                flags=re.I)
    if '<COURSECREDITS>' in requirement_name.upper():
      requirement_name = re.sub(r'<courscredits>', course_info.credits, requirement_name,
                                flags=re.I)

    context_list[-1]['requirement_name'] = requirement_name
    requirement_info['label'] = requirement_name

    data_row = [institution, requirement_id, other_requirement_ids, requirement_key, block_title,
                json.dumps(context_list + [{'requirement': requirement_info}], ensure_ascii=False),
                generated_date]

    requirements_writer.writerow(data_row)


# process_block()
# =================================================================================================
def process_block(block_info: dict,
                  context_list: list = [],
                  plan_dict: dict = None):
  """ Process a dap_req_block.
      The block will be:
        - An academic plan (major or minor)
        - A subplan (concentration)
        - A nested (“other”) requirement referenced from a plan or subplan.

      Plans are special: they are the top level of a program, and get entered into the programs
      table. The context list for requirements get initialized here with information about the
      program, including header-level requirements/restrictions, and a list of active subplans
      associated with the plan. When the plan's parse tree is processed, any block referenced by
      a block, block_type, or copy_rules clause will be checked and, if it is of type CONC, verified
      against the plan's list of active subplans, and its context is added to the list of
      references for the subplan. If a block is neither a plan nor a subplan, its context is added
      to the list of “others” references for the plan.

      Orphans are subplans (concentrations) that are never referenced by its plan’s requirements.
  """

  institution = block_info['institution']
  requirement_id = block_info['requirement_id']
  dap_req_block_key = (institution, requirement_id)
  reference_counts[dap_req_block_key] += 1

  caller_frame = traceback.extract_stack()[-2]
  reference_callers[dap_req_block_key].append((Reference._make((caller_frame.name,
                                                                caller_frame.lineno))))

  # Every block has to have an error-free parse_tree
  if quarantine_manager.is_quarantined(dap_req_block_key):
    print(f'{institution} {requirement_id} Quarantined block (ignored)', file=log_file)
    return
  parse_tree = get_parse_tree(dap_req_block_key)

  if len(parse_tree) == 0:
    # Block not parsed yet.
    print(f'{institution} {requirement_id} Empty parse tree (ignored)', file=fail_file)
    return

  if 'error' in parse_tree.keys():
    # Should not occur
    print(f'{institution} {requirement_id} {parse_tree["error"]}', file=fail_file)
    return

  header_dict = traverse_header(institution, requirement_id, parse_tree)

  # Characterize blocks as top-level or nested for reporting purposes; use capitalization to sort
  # top-level before nested.
  toplevel_str = 'Top-level' if plan_dict else 'nested'
  print(f'{institution} {requirement_id} {toplevel_str}', file=blocks_file)

  """ A block_info object contains information about a dap_req_block. When blocks are nested, either
      as a subplan of a plan, or when referenced by a blocktype, block, or copy_rules construct, a
      block_info object is pushed onto the context_list.

      Information for block_info comes from:
        * dap_req_block metadata
        * acad_plan and acad_subplan tables
        * parse_tree header

      plan_dict:
       plan_name, plan_type, plan_description, plan_cip_code, plan_effective_date,
       requirement_id, subplans, others

      subplans: (list of subplan_dict)
        subplan_dict:
          subplan_block_info, subplan_name, subplan_type, subplan_description, subplan_cip_code,
          subplan_effective_date, subplan_active_terms, subplan_enrollment, subplan_references
          subplan_referenes: (list)
            contexts in which the subplan was referenced
      others: (list of other_dict)
        other_dict:
          other_block_info, other_references
            other_references: (list)
              contexts in which the block was referenced

      block_info_dict: (Will appear in plan_dicts, subplan_dicts, and other dicts)
        institution, requirement_id, block_type, block_value, block_title, catalog_years_str,

      header_dict: (Not part of block_info: used to populate program table, and handled here when
                    a plan_dict is received.)
        class_credits, minres_list, mingrade_list, mingpa_list, maxtransfer_list, max_classes,
        max_credits, other
  """
  catalog_years_str = catalog_years(block_info['period_start'],
                                    block_info['period_stop']).text

  block_info_dict = {'institution': institution,
                     'requirement_id': requirement_id,
                     'block_type': block_info['block_type'],
                     'block_value': block_info['block_value'],
                     'block_title': block_info['block_title'],
                     'catalog_years': catalog_years_str}

  if plan_dict:
    """ For plans, the block_info_dict, which will become context_list[0], gets updated with info
        about the plan, its subplans, and others referenced indirectly.
    """
    assert len(context_list) == 0, f'{institution} {requirement_id} plan_dict w/ non-empty context'

    plan_name = plan_dict['plan']
    plan_info_dict = {'plan_name': plan_name,
                      'plan_type': plan_dict['type'],
                      'plan_description': plan_dict['description'],
                      'plan_catalog_years': catalog_years_str,
                      'plan_effective_date': plan_dict['effective_date'],
                      'plan_cip_code': plan_dict['cip_code'],
                      'plan_active_terms': block_info['num_recent_active_terms'],
                      'plan_enrollment': block_info['recent_enrollment'],
                      'subplans': [],
                      'others': []
                      }

    for subplan in plan_dict['subplans']:
      subplan_block_info = subplan['requirement_block']
      subplan_key = (institution, subplan_block_info['requirement_id'])
      subplan_dict = {'subplan_block_info': subplan_block_info,
                      'subplan_name': subplan['subplan'],
                      'subplan_type': subplan['type'],
                      'subplan_description': subplan['description'],
                      'subplan_effective_date': subplan['effective_date'],
                      'subplan_cip_code': subplan['cip_code'],
                      'subplan_active_terms': subplan_block_info['num_recent_active_terms'],
                      'subplan_enrollment': subplan_block_info['recent_enrollment'],
                      'subplan_references': []
                      }
      plan_info_dict['subplans'].append(subplan_dict)

    block_info_dict['plan_info'] = plan_info_dict

    # Add the plan_info_dict to the programs table too, for generating the header-based catalog
    # description of the program.
    header_dict['other']['plan_info'] = plan_info_dict

  else:
    """ For non-plan blocks, look up the subplan in the plan dict, if possible
    """
    subplan_list = context_list[0]['block_info']['plan_info']['subplans']
    found = False
    for subplan in subplan_list:
      if subplan['subplan_block_info']['requirement_id'] == requirement_id:
        subplan['subplan_references'].append(mogrify_context_list(context_list))
        found = True
    if not found:
      others_list = context_list[0]['block_info']['plan_info']['others']
      others_dict = {'other_block_info': block_info,
                     'other_block_context': mogrify_context_list(context_list)
                     }
      others_list.append(others_dict)

  # Traverse the body of the block. If this is a program block, the subplan and others lists will be
  # updated by any block, blocktype, and copy_rules items encountered during the recursive traversal
  # process.
  try:
    body_list = parse_tree['body_list']
  except KeyError:
    print(institution, requirement_id, 'Missing Body', file=fail_file)
    return
  if len(body_list) == 0:
    print(institution, requirement_id, 'Empty Body', file=log_file)
  else:
    for body_item in body_list:
      # traverse_body(body_item, item_context)
      traverse_body(body_item, context_list + [{'block_info': block_info_dict}])

  # Enter the block’s header info into the programs table if it’s not already there
  if dap_req_block_key not in program_blocks_list:
    program_blocks_list.append(dap_req_block_key)
    total_credits_col = json.dumps(header_dict["total_credits_list"], ensure_ascii=False)
    maxtransfer_col = json.dumps(header_dict["maxtransfer_list"], ensure_ascii=False)
    minres_col = json.dumps(header_dict["minres_list"], ensure_ascii=False)
    mingrade_col = json.dumps(header_dict["mingrade_list"], ensure_ascii=False)
    mingpa_col = json.dumps(header_dict["mingpa_list"], ensure_ascii=False)
    other_col = json.dumps(header_dict['other'], ensure_ascii=False)

    programs_writer.writerow([f'{institution[0:3]}',
                              f'{requirement_id}',
                              f'{block_info_dict["block_type"]}',
                              f'{block_info_dict["block_value"]}',
                              f'{block_info_dict["block_title"]}',
                              total_credits_col,
                              maxtransfer_col,
                              minres_col,
                              mingrade_col,
                              mingpa_col,
                              other_col,
                              generated_date
                              ])

  # Finish handling academic plans
  if plan_dict:
    # Log information about subplan and others references
    if (num_subplans := len(plan_dict['subplans'])) > 0:
      # Log cases where there are either zero or more than one reference to the subplan
      for subplan in block_info_dict['plan_info']['subplans']:
        num_references = len(subplan['subplan_references'])
        subplan_name = subplan['subplan_name']
        if num_references == 0:
          print(f'{institution} {requirement_id} Subplan {subplan_name} not referenced',
                file=subplans_file)
        if num_references > 1:
          print(f'{institution} {requirement_id} Subplan {subplan_name} referenced '
                f'{num_references} times', file=subplans_file)

    if (num_others := len(block_info_dict['plan_info']['others'])) > 0:
      s = '' if num_others == 1 else 's'
      print(f'{institution} {requirement_id} {num_others} Other block{s} referenced',
            file=subplans_file)


# traverse_header()
# =================================================================================================
def traverse_header(institution: str, requirement_id: str, parse_tree: dict) -> dict:
  """ Extract program-wide qualifiers, and update block_info with the values found. Handles only
      fields deemed relevant to transfer.
  """

  return_dict = dict()
  # Lists of limits that might or might not be specified in the header. Each is a list of dicts

  #  Separate columns, which are populated with list of dicts:
  #    Total Credits
  #    Max Transfer
  #    Min Residency
  #    Min Grade
  #    Min GPA
  for key in ['total_credits_list',
              'maxtransfer_list',
              'minres_list',
              'mingrade_list',
              'mingpa_list']:
    return_dict[key] = []

  # The ignomious 'other' column: a dict of lists of dicts
  return_dict['other'] = {'maxclass_list': [],
                          'maxcredit_list': [],
                          'maxpassfail_list': [],
                          'maxperdisc_list': [],
                          'minclass_list': [],
                          'mincredit_list': [],
                          'minperdisc_list': [],
                          'proxyadvice_list': [],
                          'conditional_dict': []}

  try:
    if len(parse_tree['header_list']) == 0:
      print(f'{institution} {requirement_id} Empty Header', file=log_file)
      return return_dict
  except KeyError as ke:
    # Should not occur
    parse_tree = exit(f'{institution} {requirement_id} Invalid parse_tree: {parse_tree}')

  for header_item in parse_tree['header_list']:

    if not isinstance(header_item, dict):
      exit(f'{institution} {requirement_id} Header “{header_item}” is not a dict')

    for key, value in header_item.items():
      match key:

        case 'header_class_credit':
          # ---------------------------------------------------------------------------------------

          return_dict['total_credits_list'].append(header_classcredit(institution, requirement_id,
                                                                      value, do_proxyadvice))

        case 'conditional':
          # ---------------------------------------------------------------------------------------
          """ Observed:
                No course list items
                 58   T: ['header_class_credit']
                 30   F: ['header_class_credit']
                 49   T: ['header_share']
                 49   F: ['header_share']
                  7   T: ['header_minres']

                With course list items
                The problem is that many of these expand to un-useful lists of courses, but others
                are meaningful. Need to look at them in more detail.
                 15   T: ['header_maxcredit']
                  1   T: ['header_maxtransfer']
                  2   T: ['header_minclass']
                  5   T: ['header_mincredit']
                  1   F: ['header_mincredit']

                Recursive item
                 28   F: ['conditional_dict']
          """
          print(f'{institution} {requirement_id} Header conditional', file=log_file)
          header_conditional(institution, requirement_id, return_dict, header_item)

        case 'header_lastres':
          # ---------------------------------------------------------------------------------------
          # A subset of residency requirements
          print(f'{institution} {requirement_id} Header lastres (ignored)', file=log_file)
          pass

        case 'header_maxclass':
          # ---------------------------------------------------------------------------------------
          print(f'{institution} {requirement_id} Header maxclass', file=log_file)
          return_dict['other']['maxclass_list'].append(header_maxclass(institution, requirement_id,
                                                                       value))

        case 'header_maxcredit':
          # ---------------------------------------------------------------------------------------
          print(f'{institution} {requirement_id} Header maxcredit', file=log_file)
          return_dict['other']['maxcredit_list'].append(header_maxcredit(institution,
                                                                         requirement_id,
                                                                         value))

        case 'header_maxpassfail':
          # ---------------------------------------------------------------------------------------
          print(f'{institution} {requirement_id} Header maxpassfail', file=log_file)
          return_dict['other']['maxpassfail_list'].append(header_maxpassfail(institution,
                                                                             requirement_id,
                                                                             value))

        case 'header_maxperdisc':
          # ---------------------------------------------------------------------------------------
          print(f'{institution} {requirement_id} Header maxperdisc', file=log_file)
          return_dict['other']['maxperdisc_list'].append(header_maxperdisc(institution,
                                                                           requirement_id, value))

        case 'header_maxtransfer':
          # ---------------------------------------------------------------------------------------
          print(f'{institution} {requirement_id} Header maxtransfer', file=log_file)
          return_dict['maxtransfer_list'].append(header_maxtransfer(institution, requirement_id,
                                                                    value))

        case 'header_minclass':
          # ---------------------------------------------------------------------------------------
          print(f'{institution} {requirement_id} Header minclass', file=log_file)
          return_dict['other']['minclass_list'].append(header_minclass(institution,
                                                                       requirement_id, value))

        case 'header_mincredit':
          # ---------------------------------------------------------------------------------------
          print(f'{institution} {requirement_id} Header mincredit', file=log_file)
          return_dict['other']['mincredit_list'].append(header_mincredit(institution,
                                                                         requirement_id, value))

        case 'header_mingpa':
          # ---------------------------------------------------------------------------------------
          print(f'{institution} {requirement_id} Header mingpa', file=log_file)
          return_dict['mingpa_list'].append(header_mingpa(institution, requirement_id, value))

        case 'header_mingrade':
          # ---------------------------------------------------------------------------------------
          print(f'{institution} {requirement_id} Header mingrade', file=log_file)
          return_dict['mingrade_list'].append(header_mingrade(institution, requirement_id, value))

        case 'header_minperdisc':
          # ---------------------------------------------------------------------------------------
          print(f'{institution} {requirement_id} Header minperdisc', file=log_file)
          return_dict['other']['minperdisc_list'].append(header_minperdisc(institution,
                                                                           requirement_id, value))

        case 'header_minres':
          # ---------------------------------------------------------------------------------------
          print(f'{institution} {requirement_id} Header minres', file=log_file)
          return_dict['minres_list'].append(header_minres(institution, requirement_id, value))

        case 'proxy_advice':
          # ---------------------------------------------------------------------------------------
          if do_proxyadvice:
            return_dict['other']['proxyadvice_list'].append(value)
            print(f'{institution} {requirement_id} Header {key}', file=log_file)
          else:
            print(f'{institution} {requirement_id} Header {key} (ignored)', file=log_file)

        case 'remark':
          # ---------------------------------------------------------------------------------------
          # (Not observed to occur)
          print(f'{institution} {requirement_id} Header remark', file=log_file)
          assert 'remark' not in return_dict['other'].keys()
          return_dict['other']['remark'] = value

        case 'header_maxterm' | 'header_minterm' | 'lastres' | 'noncourse' | 'optional' | \
             'rule_complete' | 'standalone' | 'header_share' | 'header_tag' | 'under':
          # ---------------------------------------------------------------------------------------
          # Intentionally ignored: there are no course requirements or restrictions to report for
          # these.
          print(f'{institution} {requirement_id} Header {key} (ignored)', file=log_file)
          pass

        case _:
          # ---------------------------------------------------------------------------------------
          print(f'{institution} {requirement_id}: Unexpected {key} in header', file=sys.stderr)

  return return_dict


# traverse_body()
# =================================================================================================
def traverse_body(node: Any, context_list: list) -> None:
  """ Extract Requirement names and course lists from body rules. Unlike traverse_header(), which
      makes a single pass over all the elements in the header list for a Scribe Block, this is a
      recursive function to handle nested requirements.

      Element 0 of the context list is always information about the block, including header
      restrictions: MaxTransfer, MinResidency, MinGrade, and MinGPA. (See traverse_header(), which
      adds this info to the BlockInfo object in the context_list.)

      If there is a label, that becomes the requirement_name to add to the context_list when
      entering sub-dicts.

      Block, Conditional, CopyRules, Groups, and Subsets all have to be handled individually here.

      If a node's subdict has a course_list, that becomes an output.

        body_rule       : block
                        | blocktype
                        | class_credit
                        | conditional
                        | course_list_rule
                        | copy_rules
                        | group_requirement
                        | noncourse
                        | proxy_advice
                        | remark
                        | rule_complete
                        | subset
  """

  global do_remarks, args

  # Get the program block_type and block_value from the first element of the context_list
  program_block_type = context_list[0]['block_info']['block_type']
  program_block_value = context_list[0]['block_info']['block_value']
  nested_blocks = []
  for context_item in context_list:
    try:
      nested_blocks.append(context_item['block_info'])
    except KeyError:
      pass
  nested_block_values = [block_info['block_value'] for block_info in nested_blocks]
  nested_block_requirement_ids = [block_info['requirement_id'] for block_info in nested_blocks]
  # Eliminate duplicates while preserving order (does nothing!)
  nested_block_values = list(dict.fromkeys(nested_block_values))

  # The path of requirement_ids to the current block
  requirement_ids = ':'.join(list(dict.fromkeys(nested_block_requirement_ids)))

  # The containing block’s context is the last block_info in the context list
  block_info = nested_blocks[-1]
  institution = block_info['institution']
  requirement_id = block_info['requirement_id']
  block_type = block_info['block_type']
  block_value = block_info['block_value']
  block_title = block_info['block_title']

  # Handle lists
  if isinstance(node, list):
    for item in node:
      traverse_body(item, context_list)

  elif isinstance(node, dict):
    # A dict should have one key that identifies the requirement type, and a sub-dict that gives the
    # details about that requirement, including the label that gives it its name.
    assert len(node) == 1, f'{list(node.keys())}'
    requirement_type, requirement_value = list(node.items())[0]

    # String values are remarks: add to context, and continue. Can be suppressed from command line.
    if isinstance(requirement_value, str):
      assert requirement_type == 'remark'
      if do_remarks:
        print(f'{institution} {requirement_id} Body remark',
              file=log_file)
        context_list += [{requirement_type: requirement_value}]
      else:
        pass

    # Lists happen in requirement_values because of how the grammar handles requirements that can
    # occur in different orders. (“This or that, zero or more times.”)
    elif isinstance(requirement_value, list):
      for list_item in requirement_value:
        traverse_body(list_item, context_list)

    elif isinstance(requirement_value, dict):
      context_dict = get_restrictions(requirement_value)
      try:
        context_dict['requirement_name'] = requirement_value['label']
        print(f'{institution} {requirement_id} {requirement_value["label"]}', file=label_file)
      except KeyError:
        # Unless a conditional, if there is no label, add a placeholder name, and log the situation
        if requirement_type != 'conditional':
          context_dict['requirement_name'] = 'Unnamed Requirement'
          if requirement_type not in ['copy_rules']:  # There may be others (?) ...
            print(f'{institution} {requirement_id} Body {requirement_type} with no label',
                  file=log_file)
      requirement_context = [context_dict]

      match requirement_type:

        case 'block':
          # ---------------------------------------------------------------------------------------
          # The number of blocks has to be 1, and there has to be a matching block_type/value block
          num_required = int(requirement_value['number'])

          if num_required != 1:
            print(f'{institution} {requirement_id} Body block: {num_required=}', file=todo_file)
          else:
            block_args = [requirement_value['institution'],
                          requirement_value['block_type'],
                          requirement_value['block_value']]

            if block_args[2].lower().startswith('mhc'):
              # Ignore Honors College requirements
              pass

            else:
              with psycopg.connect('dbname=cuny_curriculum') as conn:
                with conn.cursor(row_factory=dict_row) as cursor:
                  blocks = cursor.execute("""
                  select institution, requirement_id, block_type, block_value, title as block_title,
                         period_start, period_stop, major1
                    from requirement_blocks
                   where term_info is not null
                     and institution = %s
                     and block_type = %s
                     and block_value = %s
                  """, block_args)

                  target_block = None

                  if cursor.rowcount == 0:
                    print(f'{institution} {requirement_id} Body block: no active {block_args[1:]} '
                          f'blocks', file=fail_file)

                  elif cursor.rowcount > 1:
                    # Hopefully, the major1 field of exactly one block will match this program's
                    # block value, resolving the issue.
                    matching_rows = []
                    for row in cursor:
                      if row['major1'] in nested_block_values:
                        matching_rows.append(row)
                        """
                        print(nested_block_values.index(row['major1']),
                              f'of {len(nested_block_values)} {nested_block_values}',
                              file=sys.stderr)
1 of 2 ['CET-BA', 'RUS-BA']
1 of 2 ['ECETSE-BA', 'RUS-BA']
1 of 2 ['ECHE-BA', 'RUS-BA']

BKL01 RA002573 Body block: 2 active ['CONC', 'RUSSIAN'] blocks; 0 major1 = CET-BA matches
BKL01 RA000523 Body block: 2 active ['CONC', 'RUSSIAN'] blocks; 2 major1 = ECETSE-BA matches
BKL01 RA002902 Body block: 2 active ['CONC', 'RUSSIAN'] blocks; 0 major1 = ECHE-BA matches
                        """
                    if len(matching_rows) == 1:
                      target_block = matching_rows[0]
                    else:
                      print(f'{institution} {requirement_id} Body block: {cursor.rowcount} active '
                            f'{block_args[1:]} blocks; {len(matching_rows)} major1 = '
                            f'{program_block_value} matches',
                            file=fail_file)
                  else:
                    target_block = cursor.fetchone()

                  if target_block is not None:
                    process_block(target_block, context_list + requirement_context)
                    print(f'{institution} {requirement_id} Body block {target_block["block_type"]}',
                          file=log_file)

        case 'blocktype':
          # ---------------------------------------------------------------------------------------
          # Presumably, this is a reference to a subplan (concentration) for a plan.
          # Preconditions are:
          #   This block is for a plan
          #   This plan has to have at least one active plan
          #   There is at least one matching CONC block

          preconditions = True

          # Is this a plan with active subplans?:
          try:
            active_subplans = block_info['plan_info']['subplans']
          except KeyError as err:
            print(f'{institution} {requirement_id} Body blocktype: from non-plan block',
                  file=fail_file)
            preconditions = False

          if len(active_subplans) < 1:
            print(f'{institution} {requirement_id} Body blocktype: plan has no active subplans',
                  file=fail_file)
            preconditions = False

          # Required blocktype is not CONC
          required_blocktype = requirement_value['block_type']
          if required_blocktype != 'CONC':
            print(f'{institution} {requirement_id} Body blocktype: required blocktype is '
                  f'{required_blocktype} (ignored)', file=fail_file)
            preconditions = False

          if preconditions:

            # Log cases where multiple blocks are required
            num_required = int(requirement_value['number'])
            if num_required > 1:
              print(f'{institution} {requirement_id} Body blocktype: {num_required} subplans '
                    f'required', file=log_file)

            num_subplans = len(active_subplans)
            s = '' if num_subplans == 1 else 's'
            num_subplans_str = f'{num_subplans} subplan{s}'

            for active_subplan in active_subplans:
              process_block(active_subplan['subplan_block_info'],
                            context_list + requirement_context)

            print(f'{institution} {requirement_id} Block blocktype: {num_subplans_str}',
                  file=log_file)

        case 'class_credit':
          # ---------------------------------------------------------------------------------------
          print(institution, requirement_id, 'Body class_credit', file=log_file)
          # This is where course lists turn up, in general.
          try:
            if course_list := requirement_value['course_list']:
              map_courses(institution, requirement_ids, block_title,
                          context_list + requirement_context, requirement_value)
          except KeyError:
            # Course List is an optional part of ClassCredit
            pass

        case 'conditional':
          # ---------------------------------------------------------------------------------------
          assert isinstance(requirement_value, dict)
          body_conditional(institution, requirement_id, context_list, requirement_value)
          print(institution, requirement_id, 'Body conditional', file=log_file)

        case 'copy_rules':
          # ---------------------------------------------------------------------------------------
          # Get rules from target block, which must come from same institution
          target_requirement_id = requirement_value['requirement_id']

          with psycopg.connect('dbname=cuny_curriculum') as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
              cursor.execute("""
              select institution, requirement_id, block_type, block_value, title as block_title,
                     period_start, period_stop, parse_tree
                from requirement_blocks
               where institution = %s
                 and requirement_id = %s
                 and period_stop ~* '^9'
              """, (institution, target_requirement_id))
              if cursor.rowcount != 1:
                print(f'{institution} {requirement_id} Body copy_rules: {target_requirement_id} not'
                      f' current', file=fail_file)

              else:
                row = cursor.fetchone()

                is_circular = False
                for context_dict in context_list:
                  try:
                    # There cannot be cross-institutional course requirements, so this is safe
                    if row['requirement_id'] == context_dict['requirement_id']:
                      print(institution, requirement_id, 'Body circular copy_rules', file=fail_file)
                      is_circular = True
                  except KeyError:
                    pass

                if not is_circular:
                  parse_tree = row['parse_tree']
                  if parse_tree == '{}':
                    # Not expecting to do this
                    print(f'{row.institution} {row.requirement_id} Body copy_rules parse target: '
                          f'{row.requirement_id}', file=log_file)
                    parse_tree = parse_block(row['institution'], row['requirement_id'],
                                             row['period_start'], row['period_stop'])
                  if 'error' in parse_tree.keys():
                    print(f'{institution} {requirement_id} Body copy_rules {parse_tree["error"]}',
                          file=fail_file)
                  else:
                    try:
                      body_list = parse_tree['body_list']
                    except KeyError as err:
                      exit(f'{institution} {requirement_id} Body copy_rules: no body_list '
                           f'{row.requirement_id}')
                    if len(body_list) == 0:
                      print(f'{institution} {requirement_id} Body copy_rules: empty body_list',
                            file=fail_file)
                    else:
                      local_dict = {'institution': institution,
                                    'requirement_id': row['requirement_id'],
                                    'requirement_name': row['block_title']}
                      local_context = [local_dict]
                      traverse_body(body_list,
                                    context_list + requirement_context + local_context)

                      print(institution, requirement_id, 'Body copy_rules', file=log_file)

        case 'course_list':
          # ---------------------------------------------------------------------------------------
          # Not observed to occur
          print(institution, requirement_id, 'Body course_list', file=fail_file)

        case 'course_list_rule':
          # ---------------------------------------------------------------------------------------
          if 'course_list' not in requirement_value.keys():
            # Can't have a Course List Rule w/o a course list
            print(f'{institution} {requirement_id} Body course_list_rule w/o a Course List',
                  file=fail_file)
          else:
            map_courses(institution, requirement_ids, block_title,
                        context_list + requirement_context, requirement_value)
            print(institution, requirement_id, 'Body course_list_rule', file=log_file)

        case 'rule_complete':
          # ---------------------------------------------------------------------------------------
          # There are no course requirements for this, but whether “is_complete” is true or false,
          # coupled with what sort of conditional structure it is nested in, could be used to tell
          # whether a concentration is required (or not). For now, it is ignored, and unless there
          # is a group structure to hold references to other blocks (which could be used if a
          # student has to complete, say, 3 of 5 possible concentrations), assume that however many
          # concentration blocks are found, the student has to declare one and complete its
          # requirements.)
          print(institution, requirement_id, 'Body rule_complete (ignored)', file=log_file)

        case 'group_requirement':
          # ---------------------------------------------------------------------------------------
          """ Each group requirement has a group_list, label, and number (num_required)
              A group_list is a list of groups (!)
              Each group is a list of requirements block, blocktype, class_credit, course_list,
                                    group_requirement(s), noncourse, or rule_complete)
          """
          group_list = requirement_value['group_list']
          num_groups = len(group_list)
          s = '' if num_groups == 1 else 's'
          if num_groups < len(number_names):
            num_groups_str = number_names[num_groups]
          else:
            num_groups_str = f'{num_groups:,}'

          num_required = int(requirement_value['number'])
          context_dict['num_groups'] = num_groups
          context_dict['num_required'] = num_required

          # Replace common variants of the requirement_name with standard-format version
          description_str = format_group_description(num_groups, num_required)

          ignore_words = number_names + ['and', 'area', 'areas', 'choose', 'following', 'from',
                                         'group', 'groups', 'module', 'modules', 'of', 'option',
                                         'options', 'or', 'select', 'selected', 'selct', 'slect',
                                         'sequence', 'sequences', 'set', 'study', 'the']
          word_str = context_dict['requirement_name']

          # Strip digits and punctuation and extract resulting words from description string
          words = [word.lower() for word in
                   re.sub(r'[\d,:]+', ' ', word_str).split()]
          for ignore_word in ignore_words:
            try:
              del words[words.index(ignore_word)]
            except ValueError:
              pass

          # Are there any not-to-ignore words left?
          if words:
            # Yes: keep the current requirement_name.
            pass
          else:
            # No: Replace the Scribed name with our formatted one.
            context_dict['requirement_name'] = description_str

          for group_num, group in enumerate(group_list):
            if (group_num + 1) < len(number_ordinals):
              group_num_str = (f'{number_ordinals[group_num + 1].title()} of {num_groups_str} '
                               f'group{s}')
            else:
              group_num_str = f'Group number {group_num + 1:,} of {num_groups_str} group{s}'

            group_context = [{'group_number': group_num + 1,
                              'group_number_str': group_num_str}]

            for requirement in group:
              for key, value in requirement.items():
                match key:

                  case 'block':
                    # -----------------------------------------------------------------------------
                    block_name = value['label']
                    print(f'{institution} {requirement_id} {value["label"]}', file=label_file)
                    block_num_required = int(value['number'])
                    if block_num_required > 1:
                      print(f'{institution} {requirement_id} Group block: {block_num_required=}',
                            file=todo_file)
                      continue
                    block_type = value['block_type']
                    block_value = value['block_value']
                    block_institution = value['institution']
                    block_args = [block_institution, block_type, block_value]
                    with psycopg.connect('dbname=cuny_curriculum') as conn:
                      with conn.cursor(row_factory=dict_row) as cursor:
                        cursor.execute("""
                        select institution,
                                    requirement_id,
                                    block_type,
                                    block_value,
                                    title as block_title,
                                    period_start, period_stop, major1
                               from requirement_blocks
                              where term_info is not null
                                and institution = %s
                                and block_type =  %s
                                and block_value = %s
                                and period_stop ~* '^9'
                        """, [institution, block_type, block_value])

                        target_block = None
                        if cursor.rowcount == 0:
                          print(f'{institution} {requirement_id} Group block: no active '
                                f'{block_args[1:]} blocks', file=fail_file)
                        elif cursor.rowcount > 1:
                          # Hopefully, the major1 field of exactly one block will match this
                          # program's block value, resolving the issue.
                          matching_rows = []
                          for row in cursor:
                            if row['major1'] == block_value:
                              matching_rows.append(row)
                          if len(matching_rows) == 1:
                            target_block = matching_rows[0]
                          else:
                            print(f'{institution} {requirement_id} Group block: {cursor.rowcount} '
                                  f'active {block_args[1:]} blocks; {len(matching_rows)} major1 '
                                  f'matches', file=fail_file)
                        else:
                          target_block = cursor.fetchone()

                        if target_block is not None:
                          process_block(target_block, context_list + requirement_context)
                          print(f'{institution} {requirement_id} Group block '
                                f'{target_block["block_type"]}', file=log_file)

                  case 'blocktype':
                    # -----------------------------------------------------------------------------
                    # Not observed to occur
                    print(institution, requirement_id, 'Group blocktype (ignored)', file=todo_file)

                  case 'class_credit':
                    # -----------------------------------------------------------------------------
                    # This is where course lists turn up, in general.
                    try:
                      label_str = value['label']
                      print(f'{institution} {requirement_id} {value["label"]}', file=label_file)
                      map_courses(institution, requirement_ids, block_title,
                                  context_list + requirement_context + group_context +
                                  [{'requirement_name': label_str}], value)
                    except KeyError as ke:
                      # Course List is an optional part of ClassCredit
                      pass
                    print(institution, requirement_id, 'Group class_credit', file=log_file)

                  case 'course_list_rule':
                    # -----------------------------------------------------------------------------
                    if 'course_list' not in requirement_value.keys():
                      # Can't have a Course List Rule w/o a course list
                      print(f'{institution} {requirement_id} Group course_list_rule w/o a Course '
                            f'List', file=fail_file)
                    else:
                      map_courses(institution, requirement_ids, block_title,
                                  context_list + group_context, value)
                      print(institution, requirement_id, 'Group course_list_rule', file=log_file)

                  case 'group_requirement':
                    # -----------------------------------------------------------------------------
                    print(institution, requirement_id, 'Body nested group_requirement',
                          file=log_file)
                    assert isinstance(value, dict)
                    traverse_body(requirement, context_list + requirement_context + group_context)

                  case 'noncourse':
                    # -----------------------------------------------------------------------------
                    print(f'{institution} {requirement_id} Group noncourse (ignored)',
                          file=log_file)

                  case 'rule_complete':
                    # -----------------------------------------------------------------------------
                    # Not observed to occur
                    print(f'{institution} {requirement_id} Group rule_complete', file=todo_file)

                  case _:
                    # -----------------------------------------------------------------------------
                    exit(f'{institution} {requirement_id} Unexpected Group {key}')

          print(institution, requirement_id, 'Body group_requirement', file=log_file)

        case 'subset':
          print(institution, requirement_id, 'Body subset', file=log_file)
          # ---------------------------------------------------------------------------------------
          # Process the valid rules in the subset

          # Track MaxTransfer and MinGrade restrictions (qualifiers).
          context_dict = get_restrictions(requirement_value)

          try:
            context_dict['requirement_name'] = requirement_value['label']
            print(f'{institution} {requirement_id} {requirement_value["label"]}', file=label_file)
          except KeyError:
            context_dict['requirement_name'] = 'No requirement name available'
            print(f'{institution} {requirement_id} Subset with no label', file=fail_file)

          # Remarks and Proxy-Advice (not observed to occur)
          try:
            context_dict['remark'] = requirement_value['remark']
            print(f'{institution} {requirement_id} Subset remark', file=log_file)
          except KeyError:
            # Remarks are optional
            pass

          try:
            context_dict['proxy_advice'] = requirement_value['proxy_advice']
            print(f'{institution} {requirement_id} Subset proxy_advice', file=log_file)
          except KeyError:
            # Display/Proxy-Advice are optional
            pass

          subset_context = [context_dict]

          # The requirement_value should be a list of requirement_objects. The subset context
          # provides information for the whole subset; each requirement takes care of its own
          # context.
          for requirement in requirement_value['requirements']:
            assert len(requirement.keys()) == 1, f'{requirement.keys()}'

            for key, rule in requirement.items():

              match key:

                case 'block':
                  # -------------------------------------------------------------------------------
                  # label number type value
                  num_required = int(rule['number'])
                  if num_required != 1:
                    print(f'{institution} {requirement_id} Subset block: {num_required=}',
                          file=fail_file)
                    continue
                  block_label = rule['label']
                  print(f'{institution} {requirement_id} {rule["label"]}', file=label_file)
                  required_block_type = rule['block_type']
                  required_block_value = rule['block_value']
                  block_args = [institution, required_block_type, required_block_value]

                  # CONC, MAJOR, and MINOR blocks must be active blocks; other (literally and
                  # figuratively) blocks need only be current.
                  with psycopg.connect('dbname=cuny_curriculum') as conn:
                    with conn.cursor(row_factory=dict_row) as cursor:

                      cursor.execute("""
                      select institution, requirement_id, block_type, block_value,
                             title as block_title, period_start, period_stop, major1
                        from requirement_blocks
                       where term_info is not null
                         and institution = %s
                         and block_type = %s
                         and block_value = %s
                      """, block_args)

                      target_block = None
                      if cursor.rowcount == 0:
                        print(f'{institution} {requirement_id} Subset block: no active '
                              f'{block_args[1:]} blocks', file=fail_file)
                      elif cursor.rowcount > 1:
                        # Hopefully, the major1 field of exactly one block will match this
                        # program's block value, resolving the issue.
                        matching_rows = []
                        for row in cursor:
                          if row['major1'] == block_value:
                            matching_rows.append(row)
                        if len(matching_rows) == 1:
                          target_block = matching_rows[0]
                        else:
                          print(f'{institution} {requirement_id} Subset block: {cursor.rowcount} '
                                f'active {block_args[1:]} blocks; {len(matching_rows)} major1 '
                                f'matches', file=fail_file)
                      else:
                        target_block = cursor.fetchone()

                      if target_block is not None:
                        process_block(target_block, context_list + requirement_context)
                        print(f'{institution} {requirement_id} Subset block '
                              f'{target_block["block_type"]}', file=log_file)

                case 'blocktype':
                  # -------------------------------------------------------------------------------
                  # Not observed to occur
                  print(f'{institution} {requirement_id} Subset blocktype (ignored)',
                        file=todo_file)

                case 'conditional':
                  # -------------------------------------------------------------------------------
                  print(f'{institution} {requirement_id} Subset conditional', file=log_file)
                  body_conditional(institution, requirement_id, context_list + subset_context, rule)

                case 'copy_rules':
                  # -------------------------------------------------------------------------------
                  # Get rules from target block, which must come from same institution
                  target_requirement_id = rule['requirement_id']

                  with psycopg.connect('dbname=cuny_curriculum') as conn:
                    with conn.cursor(row_factory=namedtuple_row) as cursor:
                      cursor.execute("""
                      select institution,
                             requirement_id,
                             block_type,
                             block_value,
                             title as block_title,
                             period_start,
                             period_stop,
                             parse_tree
                        from requirement_blocks
                       where institution = %s
                         and requirement_id = %s
                         and period_stop ~* '^9'
                      """, [institution, target_requirement_id])

                      if cursor.rowcount != 1:
                        print(f'{institution} {requirement_id} Subset copy_rules: '
                              f'{target_requirement_id} not current',
                              file=fail_file)
                      else:
                        row = cursor.fetchone()
                        is_circular = False
                        for context_dict in context_list:
                          try:
                            # There are no cross-institutional course requirements, so this is safe
                            if row.requirement_id == context_dict['block_info']['requirement_id']:
                              print(institution, requirement_id, 'Subset circular copy_rules',
                                    file=fail_file)
                              is_circular = True
                          except KeyError as err:
                            pass

                        if not is_circular:
                          parse_tree = row.parse_tree
                          if parse_tree == '{}':
                            print(f'{institution} {requirement_id} Subset copy_rules: parse '
                                  f'{row.requirement_id}', file=log_file)
                            parse_tree = parse_block(row.institution, row.requirement_id,
                                                     row.period_start, row.period_stop)

                          if 'error' in parse_tree.keys():
                            problem = parse_tree['error']
                            print(f'{institution} {requirement_id} Subset copy_rules target '
                                  f'{row.requirement_id}: {problem}', file=fail_file)
                          else:
                            body_list = parse_tree['body_list']
                            if len(body_list) == 0:
                              print(f'{institution} {requirement_id} Subset copy_rules target '
                                    f'{row.requirement_id}: empty body_list',
                                    file=fail_file)
                            else:
                              local_dict = {'institution': institution,
                                            'requirement_id': target_requirement_id,
                                            'requirement_name': row.block_title}
                              local_context = [local_dict]
                              traverse_body(body_list,
                                            context_list + requirement_context + local_context)

                              print(institution, requirement_id, 'Subset copy_rules', file=log_file)

                case 'course_list_rule':
                  # -------------------------------------------------------------------------------
                  if 'course_list' not in rule.keys():
                    # Can't have a Course List Rule w/o a course list
                    print(f'{institution} {requirement_id} Subset course_list_rule w/o a '
                          f'course_list', file=fail_file)
                  else:
                    map_courses(institution, requirement_ids, block_title,
                                context_list + requirement_context,
                                rule)
                    print(f'{institution} {requirement_id} Subset course_list_rule', file=log_file)

                case 'class_credit':
                  # -------------------------------------------------------------------------------
                  if isinstance(rule, list):
                    rule_dicts = rule
                  else:
                    rule_dicts = [rule]
                  for rule_dict in rule_dicts:
                    local_dict = get_restrictions(rule_dict)
                    try:
                      local_dict['requirement_name'] = rule_dict['label']
                      print(f'{institution} {requirement_id} {rule_dict["label"]}', file=label_file)
                    except KeyError as ke:
                      print(f'{institution} {requirement_id} '
                            f'Subset class_credit with no label', file=todo_file)
                    # for k, v in rule_dict.items():

                    #   if local_dict:
                    #     local_context = [local_dict]
                    #   else:
                    #     local_context = []
                    try:
                      map_courses(institution, requirement_ids, block_title,
                                  context_list + subset_context + [local_dict],
                                  rule_dict)
                    except KeyError as err:
                      print(f'{institution} {requirement_id} {block_title} '
                            f'KeyError ({err}) in subset class_credit', file=sys.stderr)
                      exit(rule)
                  print(f'{institution} {requirement_id} Subset {key}', file=log_file)

                case 'group_requirement':
                  # -------------------------------------------------------------------------------
                  traverse_body(requirement, context_list + subset_context)
                  print(f'{institution} {requirement_id} Subset group_requirement', file=log_file)

                case 'maxpassfail' | 'maxperdisc' | 'mingpa' | 'minspread' | 'noncourse' | 'share':
                  # -------------------------------------------------------------------------------
                  # Ignored Qualifiers and rules
                  print(f'{institution} {requirement_id} Subset {key} (ignored)', file=log_file)

                case 'proxy_advice':
                  # -------------------------------------------------------------------------------
                  # Validity check
                  for context in subset_context:
                    if 'proxy_advice' in context.keys():
                      exit(f'{institution} {requirement_id} Subset context with repeated '
                           f'proxy_advice')

                  if do_proxyadvice:
                    subset_context[-1]['proxy_advice'] = rule
                    print(f'{institution} {requirement_id} Subset {key}', file=log_file)
                  else:
                    print(f'{institution} {requirement_id} Subset {key} (ignored)', file=log_file)

                case _:
                  # -------------------------------------------------------------------------------
                  print(f'{institution} {requirement_id} Unhandled Subset {key=}: '
                        f'{str(type(rule)):10} {len(rule)}', file=sys.stderr)

        case 'remark':
          # ---------------------------------------------------------------------------------------
          if do_remarks:
            print(f'{institution} {requirement_id} Body remark', file=todo_file)
          else:
            print(f'{institution} {requirement_id} Body remark (ignored)', file=log_file)

        case 'proxy_advice':
          # ---------------------------------------------------------------------------------------
          if do_proxyadvice:
            print(f'{institution} {requirement_id} Body {requirement_type}', file=todo_file)
          else:
            print(f'{institution} {requirement_id} Body {requirement_type} (ignored)',
                  file=log_file)

        case 'noncourse':
          # ---------------------------------------------------------------------------------------
          # Ignore this
          print(f'{institution} {requirement_id} Body {requirement_type} (ignored)', file=log_file)

        case _:
          # ---------------------------------------------------------------------------------------
          # Fatal error
          exit(f'{institution} {requirement_id} Unhandled Requirement Type: {requirement_type}'
               f' {requirement_value}')
  else:
    # Another fatal error: not a list, str, or dict
    exit(f'{institution} {requirement_id} Unhandled node type {type(node)} ({node})')


# main()
# -------------------------------------------------------------------------------------------------
if __name__ == "__main__":
  """ For all recently active CUNY undergraduate plans/subplans and their requirements, generate
      CSV tables for the programs, their requirements, and course-to-requirement mappings.

      An academic plan may be eithr a major or a minor. Note, however, that minors are not required
      for a degree, but at least one major is always required.

      For a plan/subplan to be mapped here, it must be recently-active as defined in activeplans.py.
      That is, it must an approved program with a current dap_req_block giving the requireents for
      the program, and there must be students currently attending the institution who have declared
      their enrollment in the plan or subplan.
  """
  start_time = datetime.datetime.now()
  parser = ArgumentParser()
  parser.add_argument('-a', '--all', action='store_true')
  parser.add_argument('-d', '--debug', action='store_true')
  parser.add_argument('--do_degrees', action='store_true')
  parser.add_argument('--no_proxy_advice', action='store_true')
  parser.add_argument('--no_remarks', action='store_true')
  parser.add_argument('--concise_conditionals', '-c', action='store_true')
  args = parser.parse_args()

  do_degrees = args.do_degrees

  do_proxyadvice = not args.no_proxy_advice
  do_remarks = not args.no_remarks

  empty_tree = "'{}'"

  programs_writer.writerow(['Institution',
                            'Requirement ID',
                            'Type',
                            'Code',
                            'Title',
                            'Total Credits',
                            'Max Transfer',
                            'Min Residency',
                            'Min Grade',
                            'Min GPA',
                            'Other',
                            'Generate Date'])

  requirements_writer.writerow(['Institution',
                                'Requirement ID',
                                'Other Requirement IDs',
                                'Requirement Key',
                                'Program Name',
                                'Context',
                                'Generate Date'])

  map_writer.writerow(['Requirement Key',
                       'Course ID',
                       'Career',
                       'Course',
                       'With',
                       'Generate Date'])

  block_types = defaultdict(int)
  programs_count = 0

  for acad_plan in active_plans():
    programs_count += 1
    requirement_block = acad_plan['requirement_block']
    block_types[requirement_block['block_type']] += 1
    if requirement_block['block_type'] not in ['MAJOR', 'MINOR']:
      # We can handle this, but it should be noted.
      print(f"{requirement_block['institution']} {requirement_block['requirement_id']} "
            f"{requirement_block['block_value']} with block type {requirement_block['block_type']}",
            file=anomaly_file)
    process_block(requirement_block, context_list=[], plan_dict=acad_plan)

  # Summary
  print(f'{programs_count:5,} Blocks')
  for k, v in block_types.items():
    print(f'{v:5,} {k.title()}')

  with open('/Users/vickery/Projects/dgw_processor/block_counts.txt', 'w') as counts_file:
    print('Block           Count', file=counts_file)
    for key, value in reference_counts.items():
      i, r = key
      print(f'{i} {r} {value:2}', file=counts_file)

  with open('/Users/vickery/Projects/dgw_processor/caller_lists.txt', 'w') as caller_file:
    print('Block          List', file=caller_file)
    for key, values in reference_callers.items():
      institution, requirement_id = key
      counts = defaultdict(int)
      for value in values:
        counts[value.lineno] += 1
      counts_str = '; '.join([f'{value.lineno}={counts[value.lineno]}'])
      print(institution, requirement_id, counts_str, file=caller_file)

  print(f'\n{(datetime.datetime.now() - start_time).seconds} seconds')
