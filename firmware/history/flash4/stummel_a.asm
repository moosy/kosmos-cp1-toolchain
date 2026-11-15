; Umschalt-Stummel Hälfte A (Labels zb_*/za_* gelten in A)
                .org $fbb
zb_k_cas: ANL  P1, #$ef      ; A12 = 0 -> Hälfte B
                NOP
                JMP  k_cas
zb_k_cal_vor: ANL  P1, #$ef      ; A12 = 0 -> Hälfte B
                NOP
                JMP  k_cal_vor
zb_s_fbef: ANL  P1, #$ef      ; A12 = 0 -> Hälfte B
                NOP
                JMP  s_fbef
zb_f_boot: ANL  P1, #$ef      ; A12 = 0 -> Hälfte B
                NOP
                JMP  f_boot
za_s_ende: ORL  P1, #$10      ; A12 = 1 -> Hälfte A
                NOP
                JMP  s_ende
za_s_cal_kass: ORL  P1, #$10      ; A12 = 1 -> Hälfte A
                NOP
                JMP  s_cal_kass
za_b_f002: ORL  P1, #$10      ; A12 = 1 -> Hälfte A
                NOP
                JMP  b_f002
za_rt_f009: ORL  P1, #$10      ; A12 = 1 -> Hälfte A
                NOP
                JMP  rt_f009
za_ps_push: ORL  P1, #$10      ; A12 = 1 -> Hälfte A
                NOP
                JMP  ps_push
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
