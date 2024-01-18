#!/bin/sh

for file in blocklists/*.ipset; do
   IPSET="$(basename "$file" .ipset)"
   echo "flushing $IPSET"
   ipset flush "$IPSET"
   echo "loading $file"
   tail -n +2 "$file" | ipset restore 2>&1 | grep -v "already added"
done
