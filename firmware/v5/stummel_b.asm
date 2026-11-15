; Umschalt-Stummel (erzeugt von gen_stummel.py, 89 Byte)
                .org $1fa7
b_zb_k_cal_vor: ANL  P1, #$ef      ; A12 = 0 -> Hälfte B
                NOP
                JMP  k_cal_vor
b_zb_sf_ok: ANL  P1, #$ef      ; A12 = 0 -> Hälfte B
                NOP
                JMP  sf_ok
b_zb_f_boot: ANL  P1, #$ef      ; A12 = 0 -> Hälfte B
                NOP
                JMP  f_boot
b_zb_j_speichern: ANL  P1, #$ef      ; A12 = 0 -> Hälfte B
                NOP
                JMP  j_speichern
b_zb_j_laden: ANL  P1, #$ef      ; A12 = 0 -> Hälfte B
                NOP
                JMP  j_laden
b_zb_j_autoboot: ANL  P1, #$ef      ; A12 = 0 -> Hälfte B
                NOP
                JMP  j_autoboot
b_zb_k_teil: ANL  P1, #$ef      ; A12 = 0 -> Hälfte B
                NOP
                JMP  k_teil
b_zb_bl_suche: ANL  P1, #$ef      ; A12 = 0 -> Hälfte B
                NOP
                JMP  bl_suche
b_za_s_ende: ORL  P1, #$10      ; A12 = 1 -> Hälfte A
                NOP
                JMP  s_ende
b_za_s_cal_ui: ORL  P1, #$10      ; A12 = 1 -> Hälfte A
                NOP
                JMP  s_cal_ui
b_za_boot_warte: ORL  P1, #$10      ; A12 = 1 -> Hälfte A
                NOP
                JMP  boot_warte
b_za_job_kopf: ORL  P1, #$10      ; A12 = 1 -> Hälfte A
                NOP
                JMP  job_kopf
b_za_bl_zeige: ORL  P1, #$10      ; A12 = 1 -> Hälfte A
                NOP
                JMP  bl_zeige
b_za_inc_pc: ORL  P1, #$10
                NOP
                SEL  MB0
                JMP  inc_pc
b_za_show_error: ORL  P1, #$10
                NOP
                SEL  MB0
                JMP  show_error
b_za_wait_key: ORL  P1, #$10
                NOP
                SEL  MB0
                JMP  wait_key
b_za_run_weiter: ORL  P1, #$10
                NOP
                SEL  MB0
                JMP  run_weiter
