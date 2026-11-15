"""Rakete: Countdown mit negativen Zahlen, Abflug, Absturz bei 'Höhe' > 127 (signed)."""
import json, sys
sys.path.insert(0, '../cp1')
HLT,ANZ,VZG,AKO,LDA,ABS,ADD,SUB,SPU,VGL,SPB,VGR,VKL,NEG,UND=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15
ODR,OVF,SEG,AS1,AS2,AS3,TST,JSR,RET,PSH,POP=25,26,27,28,29,30,31,32,33,34,35
P = {
 0:(OVF,0),            # Überlauf aus: 0-1 = 255 ohne F 006
 1:(SEG,116),          # "StArt?"
 2:(TST,0),            # Ziffer = Countdown-Länge
 3:(VGL,100), 4:(SPB,6), 5:(SPU,7),
 6:(AKO,10),           # 0 -> 10
 7:(NEG,255), 8:(ADD,101),   # A = -n  (XOR 255, +1)
 9:(ABS,105),
 10:(JSR,40),          # "t  -05" zeigen
 11:(JSR,60),          # 1 s warten
 12:(LDA,105), 13:(ADD,101), 14:(ABS,105),
 15:(VGL,100), 16:(SPB,18), 17:(SPU,10),
 18:(SEG,122),         # "AbFLUG"
 19:(JSR,60),
 20:(AKO,0), 21:(ABS,105),
 22:(LDA,105), 23:(ANZ,1), 24:(VZG,150),   # Höhe mit Vorzeichen
 25:(ADD,104), 26:(ABS,105),
 27:(UND,102), 28:(VGL,100), 29:(SPB,22),  # Bit 7 aus -> weiter steigen
 30:(SEG,90),          # "CrASH"
 31:(JSR,60),
 32:(LDA,105), 33:(ANZ,1),                 # negative "Höhe" zeigen
 34:(JSR,60), 35:(JSR,60),
 36:(SPU,1),
 # Unterprogramm ZEIGE: T aus 105 als "t  -05" / "t   05"
 40:(PSH,0),
 41:(LDA,105), 42:(UND,102), 43:(VGL,100), 44:(SPB,52),
 45:(LDA,100), 46:(ODR,103), 47:(ABS,113),  # Minus
 48:(LDA,105), 49:(NEG,255), 50:(ADD,101), 51:(SPU,55),   # Betrag
 52:(AKO,0), 53:(ABS,113), 54:(LDA,105),
 55:(AS2,114), 56:(AS3,115), 57:(SEG,110),
 58:(POP,0), 59:(RET,0),
 # Unterprogramm WARTE: 1 s
 60:(VZG,250), 61:(VZG,250), 62:(VZG,250), 63:(VZG,250), 64:(RET,0),
}
D = {100:0, 101:1, 102:128, 103:64, 104:7, 105:0,
     110:120, 111:0, 112:0, 113:0, 114:0, 115:0,
     116:109, 117:120, 118:119, 119:80, 120:120, 121:83,     # S t A r t ?
     122:119, 123:124, 124:113, 125:56, 126:62, 127:61,      # A b F L U G
     90:57, 91:80, 92:119, 93:109, 94:118, 95:0}             # C r A S H
zellen = {}
for n,(b,a) in P.items(): zellen[n]=[b,a]
for n,w in D.items(): zellen[n]=[0,w]
json.dump({f'{n:03d}':zellen[n] for n in sorted(zellen)}, open('rakete.json','w'))
print(len(zellen),'Zellen')
