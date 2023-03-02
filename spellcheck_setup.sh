#! /usr/local/bin/bash

# Copy reports/labels.txt to reports/checked_labels.txt
# Run aspell manually on checked_labels.txt
read -p 'This will overwrite spell_check/ files OK? (yN) '
if [[ ${REPLY[0]} =~ ^[Yy] ]]
then
  reports_dir='./reports'
  spellcheck_dir='./spell_check'
  rm -f $spellcheck_dir/*
  sort $reports_dir/labels.txt|uniq > $spellcheck_dir/labels
  (
    cd $spellcheck_dir
    awk '{print $0 >> $1}' labels
    rm labels
    for file in *01
    do mv ${file} ${file/01/}
    done
    ls
  )

  echo Next:
  echo "  aspell -c ${spellcheck_dir}/[college]"
  echo Then:
  echo "  diff ${spellcheck_dir}/*"

else echo 'No change'
fi