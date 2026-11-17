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
  40 => "ADD#", # 40–46 ab Firmware 5.06: fester Wert, Ausgabe als  ADD #005
  41 => "SUB#",
  42 => "VGL#",
  43 => "VGR#",
  44 => "VKL#",
  45 => "UND#",
  46 => "ODR#",
  47 => "SEF",  # ab Firmware 5.06: Bild aus der Projektbank
  48 => "JOV",  # ab Firmware 6.10: Overlay laden und hinspringen (PSK k / PSK n / JOV z)
  49 => "ZUF"   # ab Firmware 6.20: Zufallszahl 0..n-1 (ZUF 0: 0..255)
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
  47 => "Zellen %s bis +5 der Bilderbank 255 als Segmentmuster anzeigen (255 = Anzeige löschen; ab Firmware 5.06)",
  48 => "Overlay: n Zellen ab %s aus Bank k des Projekts laden (PSK k, PSK n), dann dorthin springen (ab Firmware 6.10)",
  49 => "Zufallszahl 0 bis %s minus 1 in den Akku (0: 0 bis 255); Zustand in der letzten Zelle (ab Firmware 6.20)"
);

$noarg = array("HLT","RET","PSH","POP");
$jmparg = array("SPU","SPB","JSR");
$valarg = array("LDA","ABS","ADD","SUB","VGL","VGR","VKL","UND","ODR","AS1","AS2","AS3","LIA","AIS","SIU","FRD","FWR");
$adrarg = array("LIA","AIS","SIU");


if ($argc < 2) die("Usage: $argv[0] [-i] [-c] [-d] [-o] [-n names.txt] filename.json\n       -c show code\n       -d show description\n       -i show inline numerics\n       -o create filename.koa\n       -n name table: lines \"035=display_loop\" (labels instead of label_N/wert_N)\n");

$beauty = "STANDARD";
$showdesc = false;
$showcode = false;
$output = false;
$names = array();

$carg = array_shift($argv);

while ($carg = array_shift($argv)){
  if ($carg == "-i") $beauty = "INLINE"; else
  if ($carg == "-d") $showdesc = true; else
  if ($carg == "-c") $showcode = true; else
  if ($carg == "-o") $output = true; else
  if ($carg == "-n") {
    $nf = array_shift($argv);
    if (!file_exists($nf)) die("ERROR: Name table $nf not found.\n");
    foreach (file($nf) as $nl) {
      if (!preg_match('/^\s*(\d{1,3})\s*=\s*([A-Za-z_][A-Za-z0-9_]*)\s*$/', $nl, $m)) continue;
      if ((int)$m[1] > 255) continue;
      $names[str_pad((int)$m[1], 3, "0", STR_PAD_LEFT)] = $m[2];
    }
  } else
  $fn = $carg;
}

if (substr($fn,-5) == ".json"){


  if (!file_exists($fn)) die("ERROR: File not found.\n");
  $fo = str_replace(".json",".koa",$fn);
  $ins = file($fn);
  $in = json_decode(array_shift($ins),true);

} else if (substr($fn,-4) == ".bin"){
  $in = array();
  if (!file_exists($fn)) die("ERROR: File not found.\n");
  $fo = str_replace(".bin",".koa",$fn);
  $f = fopen($fn,"r");
  $c = 0;
  while ($ic = fread($f,2)){
    $line =  str_pad($c, 3, "0", STR_PAD_LEFT);
    $in[$line]=array(ord($ic[0]),ord($ic[1]));
    $c++;
  }
  fclose($f);

} else  die("ERROR: Filename does neither end with .json nor .bin \n");

ksort($in);

$labels = array();
$values = array();

foreach ($in as $line => $c){

    $c1 = $c[0];
    $c2 = $c[1];
   
    if (!array_key_exists($c1,$cmd)) die ("ERROR: Command $c1 not valid.\n");

    $co = $cmd[$c1]; 
    $c2p = str_pad($c2, 3, "0", STR_PAD_LEFT);
    $lines = str_pad($line, 3, "0", STR_PAD_LEFT);

    if (in_array($co,$jmparg)){
      $labels[$c2p] = "label_";
    }

    if ((in_array($co,$valarg) || ($co == "SEG" && $c2 != 255)) && !array_key_exists($c2p,$values)){
      $values[$c2p] = "wert_";
    }

    if (in_array($co,$adrarg)){
      $values[$c2p] = "adresse_";
    }
}


ksort($labels);
$nr = 1;
foreach ($labels as $k=>$v){
  if (isset($names[$k])) { $labels[$k] = $names[$k]; continue; }
  $labels[$k] = $v."$nr";
  $nr++;
}

ksort($values);
$vnr = 1;
$anr = 1;
foreach ($values as $k=>$v){
  if (isset($names[$k])) { $values[$k] = $names[$k]; continue; }
  if (substr($v,0,1) == "a"){
    $values[$k] = $v."$anr";
    $anr++;
  } else {
    $values[$k] = $v."$vnr";
    $vnr++;
  }  
}

$lastline = -1;
foreach ($in as $line => $c){

    $c1 = $c[0];
    $c2 = $c[1];
 
    $co = $cmd[$c1]; 

    $c1p = str_pad($c1, 2, "0", STR_PAD_LEFT);
    $c2p = str_pad($c2, 3, "0", STR_PAD_LEFT);
    $lines = str_pad($line, 3, "0", STR_PAD_LEFT);

    $has_label = false;
    $has_line = true;
    if ($line == $lastline + 1) $has_line = false;
    
    
    if (in_array($co,$jmparg) && isset($labels[$c2p])){
      $has_label = $labels[$c2p];
    }

    if ((in_array($co,$valarg) || ($co == "SEG" && $c2 != 255)) && isset($values[$c2p])){
      $has_label = $values[$c2p];
    }
     
    $dsc = "";
    $dscarg = $c2;
    if ($has_label) $dscarg .= " ($has_label)";
    if ($showdesc) $dsc = "|  ".sprintf($cmddesc[$c1],$dscarg);

    $code = "";

    $bline = $line." ";
    $arg = $c2p;
    if ($showcode) $code = "|  $line: $c1p.$arg";
    if (!$has_line) $bline = "    ";  
    if ($has_label) $arg = $has_label;
    if (in_array($co,$noarg)) $arg = "";
    $cozeige = $co;
    if ($c1 > 0 && substr($co,-1) == "#"){ $cozeige = substr($co,0,-1); $arg = "#".$c2p; }
    // Marken mit Zeilennummer (nur zur Ansicht; der Assembler ignoriert sie und setzt sie mit -r neu)
    $marken = array();
    if (isset($names[$lines])) $marken[] = $names[$lines];
    if (isset($labels[$lines])) $marken[] = $labels[$lines];
    if (isset($values[$lines])) $marken[] = $values[$lines];
    foreach (array_unique($marken) as $mk) $btfy[] = "\n".str_pad(">$mk:", 28)."$lines";
    if (($c1>0) || ($c2>0) || array_key_exists($line,$labels) ||  array_key_exists($line,$values) || isset($names[$lines])){
      if ($has_line && !$marken) $btfy[] = "";
      $btfy[] = str_pad("  $bline$cozeige $arg ",30)."$code  $dsc";
      $lastline = $line;
    }

}

$bs = implode("\n",$btfy)."\n";
print($bs);


if ($output){
  $f = fopen($fo,"w");
  fwrite($f,$bs);
  fclose($f);
  fwrite(STDERR,"Output file $fo written.\n");
}



