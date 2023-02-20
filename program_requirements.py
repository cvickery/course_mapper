#! /usr/local/bin/python3
""" This is an interactive utility for displaying the requirements for a program (major or minor).
    If the program has any active subplans (concentrations), it prompts for the one of interest
    (unless there is only one).

    To use this, you have to know (or guess) the plan codes for the institution. You can use the
    requirement_id instead if that suits your fancy.

    For my convenience, this uses the db copy of the three CSV tables produced by the course mapper.

    Commands (Only first letter matters:
      institution   institution code
      program       program code
      r             requirement_id
      show_courses  toggle
"""


import psycopg
import sys

from psycopg.rows import namedtuple_row

if __name__ == '__main__':
  conn = psycopg.connect('dbname=cuny_curriculum')
  cursor = conn.cursor(row_factory=namedtuple_row)
  cursor.execute("""
  select code, name
    from cuny_institutions
    where associates or bachelors
  """)
  institutions = dict()
  for row in cursor:
    institutions[row.code] = row.name

  institution = None
  show_courses = False
  try:
    while reply := input('[ips]? '):
      match reply.lower()[0]:
        case 'i':
          institution = reply.split()[1].upper()[0:3] + '01'
          try:
            print(institutions[institution])
          except KeyError:
            print('Invalid institution:', institution)

        case 's':
          show_courses = not show_courses
          state = 'ON' if show_courses else 'OFF'
          print(f'Show courses is {state}')

        case 'q':
          exit()

        case _:
          print('eh?')

  except EOFError:
    exit()
