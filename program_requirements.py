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

from markdown import markdown
from psycopg.rows import namedtuple_row

institutions = dict()
with psycopg.connect('dbname=cuny_curriculum') as conn:
  with conn.cursor(row_factory=namedtuple_row) as cursor:
    cursor.execute("""
    select code, name
      from cuny_institutions
      where associates or bachelors
    """)
    for row in cursor:
      institutions[row.code] = row.name

def format_program(institution: str, program_code: str, show_courses:bool) -> str:
  """ Return Markdown-encoded description of a program’s (or subprogam’s) requirements.
  """
  with psycopg.connect('dbname=cuny_curriculum') as conn:
    with conn.cursor(row_factory=namedtuple_row) as cursor:
      cursor.execute("""
      select * from course_mapper.programs
       where institution = %s
         and code = %s
      """, (institution[0:3], program_code))
      assert cursor.rowcount == 1
      row = cursor.fetchone()
      program_name = row.title

      markdown_str = f'#{program_name} at {institutions[institution]}\n'
      markdown_str += f'##{row.requirement_id}\n'

  return markdown_str


if __name__ == '__main__':
  conn = psycopg.connect('dbname=cuny_curriculum')
  cursor = conn.cursor(row_factory=namedtuple_row)
  html_file = open('./temp.html', 'w')
  institution = None
  program_code = None
  requirement_id = None
  show_courses = False
  main_prompt = '[ips]? '
  error_prompt = 'eh? '
  prompt_str = main_prompt

  try:
    while reply := input(prompt_str):
      match reply.lower()[0]:

        case 'i':
          try:
            institution = reply.split()[1].upper()[0:3] + '01'
          except IndexError:
            prompt_str = error_prompt
            continue
          try:
            print(institutions[institution])
          except KeyError:
            print('Invalid institution:', institution)
          prompt_str = main_prompt

        case 'p':
          program_code = reply.split()[1].upper()

        case 'r':
          try:
            requirement_id = reply.split()[1]
          except IndexError:
            prompt_str = error_prompt
            continue
          try:
            requirement_id = f"RA{int(requirement_id.upper().strip('RA')):06}"
            if institution is None:
              print('No institution')
              continue
            cursor.execute("""
            select r.block_type, r.block_value, r.title as block_title, p.type, p.code
              from requirement_blocks r, course_mapper.programs p
             where r.institution = %s
               and r.requirement_id = %s
               and p.institution = %s
               and p.requirement_id = r.requirement_id
            """, (institution, requirement_id, institution[0:3]))
            if cursor.rowcount == 0:
              print(f'{requirement_id} is not an active program block at '
                    f'{institutions[institution]}')
              continue
            if cursor.rowcount > 1:
              print(f'{cursor.rowcount} rows!')
              for row in cursor():
                print(row)
              exit()
            row = cursor.fetchone()
            if row.block_value == row.code and row.block_type.startswith(row.type.upper()):
              program_code = row.block_value
              markdown_text = format_program(institution, program_code, show_courses)
              print(markdown_text)
              print(markdown(markdown_text), file=html_file)
            else:
              print(f'{row.block_type=} {row.block_value=} {row.type} {row.code=}')

          except ValueError:
            print('Invalid requirement_id:', requirement_id)
            prompt_str = main_prompt

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
