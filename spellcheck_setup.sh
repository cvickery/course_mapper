#! /usr/local/bin/bash

# Copy reports/labels.txt to reports/checked_labels.txt
# Run aspell manually on checked_labels.txt
read -p 'This will overwrite spell_check/ files OK? (yN) '
if [[ ${REPLY[0]} =~ ^[Yy] ]]
then
  reports_dir='/Users/vickery/Projects/course_mapper/reports'
  spellcheck_dir='/Users/vickery/Projects/course_mapper/spell_check'
  sort $reports_dir/labels.txt|uniq > $spellcheck_dir/labels
  cp $spellcheck_dir/labels $spellcheck_dir/labels_orig

  echo Next:
  echo "  aspell -c ${spellcheck_dir}/labels"
  echo Then:
  echo "  diff ${spellcheck_dir}/*"

else echo 'No change'
fi