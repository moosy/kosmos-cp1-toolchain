#!/usr/bin/php
<?php

function del_brackets($s){
  $o = "";
  $incl = true;
  for ($i=0; $i<strlen($s); $i++){
    $c = $s[$i];
    if ($c=="(") {$incl=false; continue;}
    if ($c==")") {$incl=true; continue;}
    if ($incl) $o .= $c;
  }
  return $o;
}


$cmd = array(
  0 => "#",
  1 => "HLT",
  2 => "ANZ",
  3 => "VZG",
  4 => "AKO",
  5 => "LDA",
  6 => "ABS",
  7 => "ADD",
  8 => "SUB",
  9 => "SPU",
  10 => "VGL",
  11 => "SPB",
  12 => "VGR",
  13 => "VKL",
  14 => "NEG",
  15 => "UND",
  16 => "P1E",
  17 => "P1A",
  18 => "P2A",
  19 => "LIA",
  20 => "AIS",
  21 => "SIU",
  22 => "P3E",
  23 => "P4A",
  24 => "P5A",
  25 => "ODR",  # 25–35 nur mit Firmware „schnell“ (ab 3.0)
  26 => "OVF",
  27 => "SEG",
  28 => "AS1",
  29 => "AS2",
  30 => "AS3",
  31 => "TST",
  32 => "JSR",
  33 => "RET",
  34 => "PSH",
  35 => "POP",
  36 => "PSK",  # 36–38 nur mit Firmware 4.0 (SPI-Flash)
  37 => "FRD",
  38 => "FWR",
  39 => "TSE",  # ab Firmware 4.02
  40 => "ADD#", # 40–46 ab Firmware 5.06: fester Wert statt Zelle, geschrieben als  ADD #5
  41 => "SUB#",
  42 => "VGL#",
  43 => "VGR#",
  44 => "VKL#",
  45 => "UND#",
  46 => "ODR#",
  47 => "SEF"   # ab Firmware 5.06: Bild aus Bank 255
);

$cmddesc = array(
  0 => "Datenwert %s",
  1 => "Halt",
  2 => "Akku-Inhalt anzeigen (001 = mit Vorzeichen, nur Firmware schnell)",
  3 => "Verzögern um %s ms",
  4 => "Konstante %s in den Akku laden",
  5 => "Inhalt von Zelle %s in den Akku laden",
  6 => "Akku-Inhalt in Zelle %s speichern",
  7 => "Zum Akku Inhalt von Zelle %s addieren",
  8 => "Vom Akku Inhalt von Zelle %s subtrahieren",
  9 => "Springe zu Adresse %s",
  10 => "Prüfen, ob Akku gleich Inhalt von Zelle %s ist",
  11 => "Wenn ja, springe zu Adresse %s",
  12 => "Prüfen, ob Akku größer als Inhalt von Zelle %s ist",
  13 => "Prüfen, ob Akku kleiner als Inhalt von Zelle %s ist",
  14 => "Akku-Inhalt bitweise mit %s verXORen (000 wie 001: 0 und 1 tauschen; Original: nur 0/1)",
  15 => "UND-Verknüpfung Akku und Zelle %s (bitweise; Original: nur 0 oder 1)",
  16 => "Klemme %s von Port 1 in Akku lesen (000 = alle)",
  17 => "Akku-Inhalt an Klemme %s von Port 1 legen (000 = alle)",
  18 => "Akku-Inhalt an Klemme %s von Port 2 legen (000 = alle)",
  19 => "Akku mit Inhalt der Zelle laden, deren Adresse unter %s steht",
  20 => "Akku in der Zelle speichern, deren Adresse unter %s steht",
  21 => "Springe zur Adresse, die in Zelle %s steht",
  22 => "Klemme %s von Port 3 in Akku lesen (000 = alle)",
  23 => "Akku-Inhalt an Klemme %s von Port 4 legen (000 = alle)",
  24 => "Akku-Inhalt an Klemme %s von Port 5 legen (000 = alle)",
  25 => "ODER-Verknüpfung Akku und Zelle %s (bitweise, nur Firmware schnell)",
  26 => "Überlauf-Fehler F-006 %s (000 = aus: 255 + 1 = 0, sonst an; nur Firmware schnell)",
  27 => "Zellen %s bis +5 als Segmentmuster anzeigen (255 = Anzeige löschen; nur Firmware schnell)",
  28 => "Hunderter des Akkus als Segmentmuster in Zelle %s (nur Firmware schnell)",
  29 => "Zehner des Akkus als Segmentmuster in Zelle %s (nur Firmware schnell)",
  30 => "Einer des Akkus als Segmentmuster in Zelle %s (nur Firmware schnell)",
  31 => "Auf Zifferntaste warten, Ziffer 0..9 in den Akku (%s; nur Firmware schnell)",
  32 => "Unterprogramm ab Adresse %s aufrufen (nur Firmware schnell)",
  33 => "Rücksprung aus dem Unterprogramm (nur Firmware schnell)",
  34 => "Akku auf den Stapel legen (nur Firmware schnell)",
  35 => "Obersten Stapelwert in den Akku holen (nur Firmware schnell)",
  36 => "Konstante %s auf den Stapel legen (nur Firmware 4.0)",
  37 => "Flash lesen: Bank, Adresse, Anzahl vom Stapel, ins RAM ab Zelle %s (nur Firmware 4.0)",
  38 => "Flash schreiben: Bank, Adresse, Anzahl vom Stapel, aus dem RAM ab Zelle %s (nur Firmware 4.0)",
  39 => "Zifferntaste seit dem letzten TSE in den Akku, sonst 255; wartet nicht (%s; nur Firmware 4.02)",
  40 => "Zum Akku den Wert %s addieren (ab Firmware 5.06)",
  41 => "Vom Akku den Wert %s subtrahieren (ab Firmware 5.06)",
  42 => "Prüfen, ob Akku gleich %s ist (ab Firmware 5.06)",
  43 => "Prüfen, ob Akku größer als %s ist (ab Firmware 5.06)",
  44 => "Prüfen, ob Akku kleiner als %s ist (ab Firmware 5.06)",
  45 => "Akku bitweise UND %s (ab Firmware 5.06)",
  46 => "Akku bitweise ODER %s (ab Firmware 5.06)",
  47 => "Zellen %s bis +5 der Bilderbank 255 als Segmentmuster anzeigen (255 = Anzeige löschen; ab Firmware 5.06)"
);

$noarg = array("HLT","RET","PSH","POP");

if ($argc < 2) die("Usage: $argv[0] [-i] [-c] [-d] [-o] [-s] [-r] filename.koa\n".
  "Options:  -c show code\n".
  "          -d show description\n".
  "          -i show inline numerics\n".
  "          -o create filename.json\n".
  "          -b create filename.bin (binary format for emulators)\n".
  "          -s create filename.json and start transfer to CP1\n".
  "          -r rewrite (beautify) input file\n");

$beauty = "STANDARD";
$showdesc = false;
$showcode = false;
$output = false;
$boutput = false;
$rewrite = false;
$send = false;

$carg = array_shift($argv);

while ($carg = array_shift($argv)){
  if ($carg == "-i") $beauty = "INLINE"; else
  if ($carg == "-d") $showdesc = true; else
  if ($carg == "-c") $showcode = true; else
  if ($carg == "-b") $boutput = true; else
  if ($carg == "-o") $output = true; else
  if ($carg == "-s") {
    $output = true;
    $send = true;
  } else
  if ($carg == "-r") $rewrite = true; else
  $fn = $carg;
}

if (substr($fn,-4) != ".koa") die("ERROR: Filename does not end with .koa\n");

$fo = str_replace(".koa",".json",$fn);
$fb = str_replace(".koa",".bin",$fn);

if (!file_exists($fn)) die("ERROR: File not found.\n");

$in = file($fn);
$labels = array();
$firstrun = true;

for ($rounds=0; $rounds<2; $rounds++){ # two identical runs for labels

  $out = array();
  $filled = array();
  $btfy = array();
  for ($i=0; $i<256; $i++){
    $filled[$i] = false;
    $key = str_pad($i, 3, "0", STR_PAD_LEFT);
    $out[$key] = array(0,0);
  }

  $lastline = -1;
  $mustsetlabel = array();
  $commentblock = false;

  foreach ($in as $l){

#    print(" +++ $l +++ \n");
    $l = trim($l);

    if (!$l) continue;
    if (substr($l,0,2)=="//"){
      $cline = "";
      if (!$commentblock) $cline = "\n";
      $commentblock = true;
      $cline .= $l;
      $btfy[] = $cline;
      continue;
    }
    if ($commentblock){
      $commentblock = false;
#      $btfy[] = "\n";
    }
    $old = "";
    while ($old != $l){
      $old = $l;
      $l = str_replace("  "," ",$l);
    }

    $l = del_brackets($l);

    $li = explode(" ",$l);

    $has_line = true;
    $has_label = false;
    $line = str_replace(":","",array_shift($li));

    if (!is_numeric($line)){

      
      if (substr($line,0,1) == ">") {  # Label
        $btfy[] = "\n".$line.":";             # Zeilennummer setzt der nächste Befehl ein (Relabel)
        $mustsetlabel[] = array(substr($line,1), count($btfy) - 1);
        continue;
      }

      # Auto-assign Cell
      $has_line = false;
      array_unshift($li,$line);  # Keine Zeilennummer -> Befehl zurück!
      $line = $lastline + 1;
    } 

    $line = str_pad($line, 3, "0", STR_PAD_LEFT);
    $cs = strtoupper(array_shift($li));
    $c1 = array_search($cs,$cmd);
    if ($c1 === false) die("ERROR: Command $cs not known (Line $line)!\n");
    $c2 = array_shift($li);
    $imm = false;
    if ($c1 > 0 && substr((string)$c2,0,1) == "#"){      # ADD #5: fester Wert (Firmware 5.06)
      $c1 = array_search($cs."#",$cmd);
      if ($c1 === false) die("ERROR: $cs has no #value form (Line $line)!\n");
      $c2 = substr($c2,1);
      if ($c2 === "") $c2 = array_shift($li);         # auch  ADD # 5
      $imm = true;
    }
    if (substr(trim($c2),0,1)=="|") $c2 = 0;
    if (substr(trim($c2),0,2)=="//") $c2 = 0;
    if (trim($c2)=="") $c2 = 0;
    if (!is_numeric($c2) && !$firstrun){
      if  (!array_key_exists($c2,$labels)) die("ERROR: Label $c2 not found! (Line $line)!\n");
      $has_label = $c2;
      $c2 = $labels[$c2];
    }
    if ($filled[(int)$line]) die("ERROR: Line $line is already set (conflict hardcoded/autoassigned line?)!\n");
    $out[$line] = array((int)$c1,(int)$c2);
    $filled[(int)$line] = true;

    foreach ($mustsetlabel as $ml){
      $labels[$ml[0]] = $line;
      $btfy[$ml[1]] = "\n".str_pad(">".$ml[0].":", 28).$line;
    }
    $mustsetlabel = array();
 
    $c2 = str_pad($c2, 3, "0", STR_PAD_LEFT);
    $dsc = "";
    $dscarg = $c2;
    if ($has_label) $dscarg .= " ($has_label)";
    if ($showdesc) $dsc = "|  ".sprintf($cmddesc[$c1],$dscarg);
    $oc  = str_pad($c1, 2, "0", STR_PAD_LEFT);
    $code = "";

    if ($beauty == "INLINE"){
      $bline = " $line ";
      $arg = $c2;
      if ($showcode) $code = "|  $line: $oc.$arg";
      if (!$has_line) $bline = "($line)";
      if ($has_label) $arg = $has_label ." ($arg)";
      if (in_array($cs,$noarg)) $arg = "";
      if ($imm) $arg = "#".$arg;
      $btfy[] = str_pad(" $bline $cs $arg",30)."$code  $dsc";
    } else {
    
      $bline = $line." ";
      $arg = $c2;
      if ($showcode) $code = "|  $line: $oc.$arg";
      if (!$has_line) $bline = "    ";
      if ($has_label) $arg = $has_label;
      if (in_array($cs,$noarg)) $arg = "";
      if ($imm) $arg = "#".$arg;
      $btfy[] = str_pad("  $bline$cs $arg ",30)."$code  $dsc";
    }
    
    
    $lastline = $line;

  }
  $firstrun = false;
}

$bs = implode("\n",$btfy)."\n";
print($bs);

print("\n");

if ($rewrite){
  $f = fopen($fn,"w"); 
  fwrite($f,$bs);
  fclose($f);
  fwrite(STDERR,"Input file $fn updated.\n");
}


if ($output){
  $f = fopen($fo,"w"); 
  fwrite($f,json_encode($out)."\n");
  fclose($f);
  fwrite(STDERR,"Output file $fo written.\n");
  if ($send) passthru("/usr/local/bin/kosmos_send.py $fo");
}

if ($boutput){
  $f = fopen($fb,"w"); 
  foreach ($out as $v){
    fwrite($f,chr($v[0]));
    fwrite($f,chr($v[1]));
  }
  fclose($f);
  fwrite(STDERR,"Binary output file $fb written.\n");
}

