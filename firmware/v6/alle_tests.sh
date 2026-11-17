#!/bin/sh
# Alle Testreihen für 6.x. Bauen: aus firmware/ python3 v6/build6.py
cd "$(dirname "$0")" || exit 1
f=0
for t in test_befehle test_tse test_ui5 test_nie5 test_fni test_flash5 test_reset test_einschalten test_blaettern test_imm test_sef test_bilder test_a14 test_projekt test_jov test_paket test_zuf; do
  echo "== $t"; out=$(python3 $t.py 2>&1); r=$?; echo "$out" | tail -1; [ $r = 0 ] || f=1
done
echo "== test_remote5"; out=$(python3 test_remote5.py 2>&1); r=$?; echo "$out" | tail -1; [ $r = 0 ] || f=1
# Umzug der gesicherten Projekte (Ordner mit .cp1 als PROJEKTE=…; die Dateien liegen nicht im Repo)
if [ -n "$PROJEKTE" ]; then echo "== test_umzug"; out=$(python3 test_umzug.py "$PROJEKTE" 2>&1); r=$?; echo "$out" | tail -1; [ $r = 0 ] || f=1; fi
[ $f = 0 ] && echo "ALLE GRÜN" || echo "FEHLER"
exit $f
