; Umschalt-Stummel (erzeugt von gen_stummel.py, 89 Byte)
                .org $fa7
zb_k_cal_vor: ANL  P1, #$ef      ; A12 = 0 -> Hälfte B
                NOP
                JMP  k_cal_vor
zb_sf_ok: ANL  P1, #$ef      ; A12 = 0 -> Hälfte B
                NOP
                JMP  sf_ok
zb_f_boot: ANL  P1, #$ef      ; A12 = 0 -> Hälfte B
                NOP
                JMP  f_boot
zb_j_speichern: ANL  P1, #$ef      ; A12 = 0 -> Hälfte B
                NOP
                JMP  j_speichern
zb_j_laden: ANL  P1, #$ef      ; A12 = 0 -> Hälfte B
                NOP
                JMP  j_laden
zb_j_autoboot: ANL  P1, #$ef      ; A12 = 0 -> Hälfte B
                NOP
                JMP  j_autoboot
zb_k_teil: ANL  P1, #$ef      ; A12 = 0 -> Hälfte B
                NOP
                JMP  k_teil
zb_bl_suche: ANL  P1, #$ef      ; A12 = 0 -> Hälfte B
                NOP
                JMP  bl_suche
za_s_ende: ORL  P1, #$10      ; A12 = 1 -> Hälfte A
                NOP
                JMP  s_ende
za_s_cal_ui: ORL  P1, #$10      ; A12 = 1 -> Hälfte A
                NOP
                JMP  s_cal_ui
za_boot_warte: ORL  P1, #$10      ; A12 = 1 -> Hälfte A
                NOP
                JMP  boot_warte
za_job_kopf: ORL  P1, #$10      ; A12 = 1 -> Hälfte A
                NOP
                JMP  job_kopf
za_bl_zeige: ORL  P1, #$10      ; A12 = 1 -> Hälfte A
                NOP
                JMP  bl_zeige
za_inc_pc: ORL  P1, #$10
                NOP
                SEL  MB0
                JMP  inc_pc
za_show_error: ORL  P1, #$10
                NOP
                SEL  MB0
                JMP  show_error
za_wait_key: ORL  P1, #$10
                NOP
                SEL  MB0
                JMP  wait_key
za_run_weiter: ORL  P1, #$10
                NOP
                SEL  MB0
                JMP  run_weiter
