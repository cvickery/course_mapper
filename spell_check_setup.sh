#! /usr/local/bin/bash

# Copy reports/labels.txt to reports/checked_labels.txt
# Run aspell manually on checked_labels.txt

reports_dir='/Users/vickery/projects/course_mapper/reports'
(
  cd $reports_dir
  sort labels.txt|uniq > unchecked_labels.txt
  cp unchecked_labels.txt checked_labels.txt
)
#
echo Next:
echo "  aspell -c ${reports_dir}/checked_labels.txt"
