#! /usr/local/bin/python3
""" Manage a cache of information about courses.
    The cache is indexed by [institution][discipline][catalog_number], is populated on demand by
    institution, and includes only active, non-message/non-bkcr courses. Cached info is course_id,
    offer_nbr, discipline, catalog_number, title, (max)credits, designation, and career.
"""

import os
import re
import sys
import psycopg

from collections import namedtuple, defaultdict
from psycopg.rows import namedtuple_row


def dict_factory():
  """ Factory needed to support the triple levels of indexing
  """
  return(defaultdict(dict))


_courses_cache = defaultdict(dict_factory)

CourseTuple = namedtuple('CourseTuple', 'course_id offer_nbr discipline catalog_number '
                         'course_title credits designation career')


# courses_cache()
# -------------------------------------------------------------------------------------------------
def courses_cache(institution: str, discipline: str, catalog_number: str) -> list:
  """
      Return a list of an institution's active courses based on one courses discipline and catalog
      number, which may include wildcards (@) in the discipline and/or catalog_number, and ranges
      (:) in the catalog number.

      Reminder to self: neither with clauses nor exclude clauses are handled here. The
      mogrify_course_list() function in the course_mapper is an example of a method that takes care
      of managing those two aspects of scribed course lists using this method to expand individual
      course references.

      Each institution’s courses are added to the cache the first time the institution is
      encountered.

      Returns a possibly-empty list of CourseTuples.
  """
  if institution not in _courses_cache.keys():
    with psycopg.connect('dbname=cuny_curriculum') as conn:
      with conn.cursor(row_factory=namedtuple_row) as cursor:
        cursor.execute("""
          select institution,
                 course_id,
                 offer_nbr,
                 discipline,
                 catalog_number,
                 title,
                 max_credits as credits,
                 designation,
                 career
            from cuny_courses
           where institution = %s
             and course_status = 'A'
             and career in ('UGRD', 'UKCC', 'ULAG', 'GRAD')
             and designation not in ('MNL', 'MLA')
             and attributes !~* 'BKCR'
             and max_credits > 0.0
           order by discipline, numeric_part(catalog_number)
        """, (institution, ))
        for row in cursor:
          info = CourseTuple._make([row.course_id,
                                    row.offer_nbr,
                                    row.discipline,
                                    row.catalog_number,
                                    row.title,
                                    row.credits,
                                    row.designation,
                                    row.career])
          _courses_cache[row.institution][row.discipline][row.catalog_number] = info

  # Simple Case
  if not ('@' in discipline or '@' in catalog_number or ':' in catalog_number):
    try:
      return [_courses_cache[institution][discipline][catalog_number]]
    except KeyError:
      return []

  # Generate list of matching disciplines
  if '@' in discipline:
    regex = f'^{discipline}$'.replace('@', '.+')
    disciplines = [key for key in _courses_cache[institution].keys() if re.match(regex, key)]
  else:
    disciplines = [discipline]

  # For each discipline, look up all the courses with matching catalog numbers.

  # Handle range of catalog numbers
  #   "A range of course numbers is indicated by separating two course numbers with a colon. The
  #    course numbers cannot contain any letters or wildcards. The lower bound (left side) must be
  #    less than or equal to the upper bound (right side)."
  if ':' in catalog_number:
    # CUNY policy says decimal points aren't allowed in catalog numbers. But they do occur, so treat
    # them as floats, which means we can't do a simple 'in range' check because ranges are ints.
    low_val, hi_val = [float(x) for x in catalog_number.split(':')]
  else:
    low_val = hi_val = None

  regex = f'^{catalog_number}$'.replace('@', '.+')

  return_list = []
  for discipline in disciplines:
    for cat_num in _courses_cache[institution][discipline].keys():
      if re.match(regex, cat_num):
        return_list.append(_courses_cache[institution][discipline][cat_num])
      elif low_val is not None:
        try:
          cat_num_val = float(cat_num)
          if cat_num_val >= low_val and cat_num_val <= hi_val:
            return_list.append(_courses_cache[institution][discipline][cat_num])
        except ValueError:
          pass

  return return_list


# main()
# -------------------------------------------------------------------------------------------------
if __name__ == '__main__':
  """ Interactive test of courses_cache()
  """
  institution = 'QNS01'
  discipline = 'CSCI'
  catalog_number = '101'
  print('? ', end='')
  while command := input():
    if command == '' or command.lower() == 'q':
      exit()
    parts = command.split()
    match len(parts):
      case 1:
        discipline = parts[0]
      case 2:
        discipline, catalog_number = parts
      case 3:
        institution, discipline, catalog_number = parts
      case _:
        print('discipline | discipline catalog # | institution discipline catalog #')
        continue
    if institution and discipline and catalog_number:
      institution = institution.strip('01').upper() + '01'
      discipline = discipline.upper()
      catalog_number = catalog_number.upper()
      print(institution, discipline, catalog_number, '\n')
      try:
        for course_tuple in courses_cache(institution, discipline, catalog_number):
          print(f'[{course_tuple.course_id:06}:{course_tuple.offer_nbr}] {course_tuple.discipline} '
                f'{course_tuple.catalog_number}: {course_tuple.title} '
                f'{course_tuple.credits}cr {course_tuple.designation} {course_tuple.career}')
      except ValueError as ve:
        print(ve)
      print('\n? ', end='')
