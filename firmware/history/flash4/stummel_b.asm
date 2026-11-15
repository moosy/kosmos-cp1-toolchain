; Umschalt-Stummel Hälfte B (gleiche Bytes)
                .org $1fbb
b_zb_k_cas: ANL  P1, #$ef      ; A12 = 0 -> Hälfte B
                NOP
                JMP  k_cas
b_zb_k_cal_vor: ANL  P1, #$ef      ; A12 = 0 -> Hälfte B
                NOP
                JMP  k_cal_vor
b_zb_s_fbef: ANL  P1, #$ef      ; A12 = 0 -> Hälfte B
                NOP
                JMP  s_fbef
b_zb_f_boot: ANL  P1, #$ef      ; A12 = 0 -> Hälfte B
                NOP
                JMP  f_boot
b_za_s_ende: ORL  P1, #$10      ; A12 = 1 -> Hälfte A
                NOP
                JMP  s_ende
b_za_s_cal_kass: ORL  P1, #$10      ; A12 = 1 -> Hälfte A
                NOP
                JMP  s_cal_kass
b_za_b_f002: ORL  P1, #$10      ; A12 = 1 -> Hälfte A
                NOP
                JMP  b_f002
b_za_rt_f009: ORL  P1, #$10      ; A12 = 1 -> Hälfte A
                NOP
                JMP  rt_f009
b_za_ps_push: ORL  P1, #$10      ; A12 = 1 -> Hälfte A
                NOP
                JMP  ps_push
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
