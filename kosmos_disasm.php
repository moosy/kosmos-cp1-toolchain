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
  24 => "P5A"
);

$cmddesc = array(
  0 => "Datenwert %s",
  1 => "Halt",
  2 => "Akku-Inhalt anzeigen",
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
  14 => "Akku-Inhalt negieren (nur 0 oder 1)",
  15 => "UND-Verknüpfung Akku und Zelle %s (nur 0 oder 1)",
  16 => "Klemme %s von Port 1 in Akku lesen (000 = alle)",
  17 => "Akku-Inhalt an Klemme %s von Port 1 legen (000 = alle)",
  18 => "Akku-Inhalt an Klemme %s von Port 2 legen (000 = alle)",
  19 => "Akku mit Inhalt der Zelle laden, deren Adresse unter %s steht",
  20 => "Akku in der Zelle speichern, deren Adresse unter %s steht",
  21 => "Springe zur Adresse, die in Zelle %s steht",
  22 => "Klemme %s von Port 3 in Akku lesen (000 = alle)",
  23 => "Akku-Inhalt an Klemme %s von Port 4 legen (000 = alle)",
  24 => "Akku-Inhalt an Klemme %s von Port 5 legen (000 = alle)"
);

$noarg = array("HLT","ANZ","NEG");
$jmparg = array("SPU","SPB");
$valarg = array("LDA","ABS","ADD","SUB","VGL","VGR","VKL","UND","LIA","AIS","SIU");
$adrarg = array("LIA","AIS","SIU");


if ($argc < 2) die("Usage: $argv[0] [-i] [-c] [-d] filename.koa\n       -c show code\n       -d show description\n       -i show inline numerics\n       -o create filename.json\n");

$beauty = "STANDARD";
$showdesc = false;
$showcode = false;
$output = false;

$carg = array_shift($argv);

while ($carg = array_shift($argv)){
  if ($carg == "-i") $beauty = "INLINE"; else
  if ($carg == "-d") $showdesc = true; else
  if ($carg == "-c") $showcode = true; else
  if ($carg == "-o") $output = true; else
  $fn = $carg;
}

if (substr($fn,-5) != ".json") die("ERROR: Filename does not end with .json\n");

$fo = str_replace(".json",".koa",$fn);

if (!file_exists($fn)) die("ERROR: File not found.\n");

$ins = file($fn);
$in = json_decode(array_shift($ins),true);

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

    if (in_array($co,$valarg) && !array_key_exists($c2p,$values)){
      $values[$c2p] = "wert_";
    }

    if (in_array($co,$adrarg)){
      $values[$c2p] = "adresse_";
    }
}


ksort($labels);
$nr = 1;
foreach ($labels as $k=>$v){
  $labels[$k] = $v."$nr";
  $nr++;
}

ksort($values);
$vnr = 1;
$anr = 1;
foreach ($values as $k=>$v){
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

    if (in_array($co,$valarg) && isset($values[$c2p])){
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
    if (isset($labels[$lines]))  $btfy[] = "\n>".$labels[$lines].":";
    if (isset($values[$lines]))  $btfy[] = "\n>".$values[$lines].":";
    if (($c1>0) || ($c2>0) || array_key_exists($line,$labels) ||  array_key_exists($line,$values)){
      if ($has_line) $btfy[] = "";
      $btfy[] = str_pad("  $bline$co $arg ",30)."$code  $dsc";
      $lastline = $line;
    }

}

$bs = implode("\n",$btfy)."\n";
print($bs);


if ($output){
  $f = fopen($fo,"w");
  fwrite($f,json_encode($out)."\n");
  fclose($f);
  fwrite(STDERR,"Output file $fo written.\n");
}



