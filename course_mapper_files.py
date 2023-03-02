#! /usr/local/bin/python3
"""
Logging/Development Report files.

  anomaly_file        Things that look wrong, but we handle anyway
  blocks_file         List of blocks processed
  fail_file           Blocks that failed for one reason or another
  log_file            Record of requirements processed successfully. Bigger is better!
  no_courses_file     Requirements with no course lists.
  subplans_file       What active subplans are (not) referenced?
  todo_file           Record of all known requirements not yet handled. Smaller is better!

Data reports for T-Rex
  programs_file       Spreadsheet of info about majors, minors, and concentrations
  requirements_file   Spreadsheet of program requirement names
  mapping_file        Spreadsheet of course-to-requirements mappings
"""
from pathlib import Path

home_dir = Path.home()
anomaly_file = Path(home_dir, 'Projects/course_mapper/reports/anomalies.txt').open(mode='w')
blocks_file = Path(home_dir, 'Projects/course_mapper/reports/blocks.txt').open(mode='w')
conditions_file = Path(home_dir, 'Projects/course_mapper/reports/conditions.txt').open(mode='w')
fail_file = Path(home_dir, 'Projects/course_mapper/reports/fail.txt').open(mode='w')
label_file = Path(home_dir, 'Projects/course_mapper/reports/labels.txt').open(mode='w')
log_file = Path(home_dir, 'Projects/course_mapper/reports/log.txt').open(mode='w')
no_courses_file = Path(home_dir, 'Projects/course_mapper/reports/no_courses.txt').open(mode='w')
subplans_file = Path(home_dir, 'Projects/course_mapper/reports/subplans.txt').open(mode='w')
todo_file = Path(home_dir, 'Projects/course_mapper/reports/todo.txt').open(mode='w')

programs_file = Path(home_dir, 'Projects/course_mapper/reports/course_mapper.programs.csv')\
    .open(mode='w', newline='')
requirements_file = Path(home_dir, 'Projects/course_mapper/reports/course_mapper.requirements.csv')\
    .open(mode='w', newline='')
mapping_file = Path(home_dir, 'Projects/course_mapper/reports/course_mapper.course_mappings.csv')\
    .open(mode='w', newline='')
