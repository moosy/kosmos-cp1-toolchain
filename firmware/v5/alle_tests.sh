#!/bin/sh
# Alle Testreihen für 5.x (alte 4.x-Reihen liegen in alt/). Aufruf aus cp1/v5.
cd "$(dirname "$0")" || exit 1
f=0
for t in test_befehle test_tse test_ui5 test_nie5 test_fni test_flash5 test_reset test_einschalten test_blaettern test_imm test_sef test_bilder; do
  echo "== $t"; out=$(python3 $t.py 2>&1); r=$?; echo "$out" | tail -1; [ $r = 0 ] || f=1
done
echo "== test_remote5"; out=$(python3 test_remote5.py 2>&1); r=$?; echo "$out" | tail -1; [ $r = 0 ] || f=1
[ $f = 0 ] && echo "ALLE GRÜN" || echo "FEHLER"
exit $f
