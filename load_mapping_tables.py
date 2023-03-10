#! /usr/local/bin/python3
"""Load the three course mapping tables into the course_mapper database.

Then you can use get_course_mapping_info.py to see what requirements a course satisfies, for
example.
"""

import argparse
import csv
import os
import sys
import psycopg

from collections import namedtuple
from datetime import date
from pathlib import Path
from psycopg.rows import namedtuple_row
from time import time


def _count_generator(reader):
    b = reader(1024 * 1024)
    while b:
        yield b
        b = reader(1024 * 1024)


if __name__ == '__main__':
  parser = argparse.ArgumentParser('Load db tables from course mappper CSV files')
  parser.add_argument('-p', '--progress', action='store_true')
  args = parser.parse_args()

  session_start = time()
  csv.field_size_limit(sys.maxsize)

  schema_name = 'course_mapper'
  with psycopg.connect('dbname=cuny_curriculum') as conn:
    with conn.cursor(row_factory=namedtuple_row) as cursor:
      cursor.execute(f'create schema if not exists {schema_name}')
      cursor.execute(f"""
      drop table if exists {schema_name}.dgw_programs,
                           {schema_name}.dgw_requirements,
                           {schema_name}.dgw_courses;""")

      cursor.execute(f"""
      create table {schema_name}.dgw_programs (
        institution     text,
        requirement_id  text,
        type            text,
        code            text,
        title           text,
        total_credits   jsonb,
        max_transfer    jsonb,
        min_residency   jsonb,
        min_grade       jsonb,
        min_gpa         jsonb,
        other           jsonb,
        generate_date   date,
        primary key (institution, requirement_id))
      """)
      conn.commit()

      cursor.execute(f"""
      create table {schema_name}.dgw_requirements (
        institution           text,
        plan_name             text,
        plan_type             text,
        subplan_name          text,
        requirement_ids       text,
        conditions            text,
        requirement_key       integer primary key,
        program_name          text,
        context               jsonb,
        generate_date         date
      )""")
      conn.commit()

      cursor.execute(f"""
      create table {schema_name}.dgw_courses (
        requirement_key  integer references {schema_name}.dgw_requirements,
        course_id        text,
        career           text,
        course           text,
        with_exp         jsonb,
        generate_date    date,
        primary key (requirement_key, course_id, with_exp)
      )""")

      cursor.execute(f"""
        update updates set update_date = CURRENT_DATE
         where table_name = '{schema_name}'
        """)

      tables = dict()
      reports_dir = Path(Path.home(), 'Projects/course_mapper/reports')
      # Sequence the tables to get the foreign key constraints in correct order
      for table_name in ['dgw_programs', 'dgw_requirements', 'dgw_courses']:
        file = Path(reports_dir, f'{table_name}.csv')
        with open(file, 'rb') as fp:
          c_generator = _count_generator(fp.raw.read)
          num_lines = sum(buffer.count(b'\n') for buffer in c_generator)
        if args.progress:
          print()
        print(f'{file.name:>20}: {num_lines:7,} lines')
        tables[table_name] = num_lines - 1
        nl = num_lines / 100.0
        with open(file) as csv_file:
          reader = csv.reader(csv_file)
          for line in reader:
            if args.progress:
              print(f'\r{reader.line_num:,}/{num_lines:,} {round(reader.line_num/nl)}%', end='')
            if reader.line_num == 1:
              Row = namedtuple('Row', [col.lower().replace(' ', '_').replace('with', 'with_exp')
                               for col in line])
              field_names = Row._fields
              fields = ',\n'.join([f'{field_name} text' for field_name in field_names])
            else:
              row = Row._make(line)
              row_dict = row._asdict()
              values = [value.replace('\'', '???') for value in row_dict.values()]
              values_arg = ','.join([f"'{value}'" for value in values])
              cursor.execute(f"""insert into {schema_name}.{table_name} values({values_arg})
                              on conflict do nothing
                              """)
              if cursor.rowcount == 0:
                print(f'{table_name} {values}', file=sys.stderr)

  for key, value in tables.items():
    print(f'{key:>20}: {value:7,} rows')

  print(f'        Elapsed Time: {round(time() - session_start):7} seconds')
