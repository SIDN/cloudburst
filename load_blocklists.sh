#!/bin/sh

for file in blocklists/*.ipset; do
   echo "loading $file"
   ipset restore --file "$file"
done
