# student-quality gate ledger

Append-only. Source of truth for G0–G7. One line per event.

## 2026-10-31T09:20:00Z preflight repo=/mnt/g/C0ding/git/wmkeyboard-wmlm branch=wmlm-de-research
## 2026-10-31T09:20:00Z preflight gpu=FAIL reason=no_dev_dri_no_dev_kfd rocminfo=hsa_init_failed torch_cuda=False windows_gpu=AMD_Radeon_RX_9060_XT driver=32.0.32015.7029
## 2026-10-31T11:09:52+01:00 start gate=G1 run=v1 steps=3000 resumed=0 distill=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_lm_2m_slice100k/soft.npz batch=256 ctx=40 d=256 layers=6 heads=4 ff=768 seed=0
## 2026-10-31T11:49:31+01:00 done gate=G1 run=v1 loss=5.1943 resumed=0
## 2026-10-31T11:49:39+01:00 start gate=G1 run=v9 steps=3000 resumed=0 distill=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_lm_2m_slice100k/soft.npz distill_align=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_lm_2m_slice100k/masks.align.npz batch=256 ctx=40 d=256 layers=6 heads=4 ff=768 seed=0
## 2026-10-31T12:29:48+01:00 done gate=G1 run=v9 loss=5.0304 resumed=0
## 2026-10-31T12:31:00+01:00 preflight_corrected gpu=OK reason=HSA_ENABLE_DXG_DETECTION_required device=AMD_Radeon_RX_9060_XT gfx=gfx1200 hip=7.2.53211 torch_cuda=True
## 2026-10-31T12:31:00+01:00 gate=G0 result=passed glide_2m=0.7848/0.8485 rows_match=yes dropped_typing=0 note=prompt_expected_dropped_gt_0_plan_expected_0 pair_2m_vs_150k=+0.00pp_CI[-0.58,+0.58]_p=1.0000 pair_2m_vs_1m2=+0.54pp_CI[+0.08,+1.00]_p=0.0385
## 2026-10-31T12:31:00+01:00 gate=G1 result=passed v1_loss=5.1943 v9_loss=5.0304 delta=-0.1639 nats step_s=1.25
## 2026-10-31T12:30:29+01:00 start gate=G2 run=v1 steps=30000 resumed=0 distill=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_soft_2m.npz batch=256 ctx=40 d=256 layers=6 heads=4 ff=768 seed=0
## 2026-10-31T19:05:58+01:00 done gate=G2 run=v1 loss=4.3087 resumed=0
## 2026-10-31T19:06:05+01:00 start gate=G2 run=v9 steps=30000 resumed=0 distill=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_soft_2m.npz distill_align=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_soft_2m.masks.align.npz batch=256 ctx=40 d=256 layers=6 heads=4 ff=768 seed=0
## 2026-11-01T01:44:07+01:00 done gate=G2 run=v9 loss=4.1711 resumed=0
## 2026-11-01T01:46:00+01:00 gate=G2 result=passed v1_loss=4.3087 v9_loss=4.1711 delta=-0.1376 nats glide_v9=0.7863 glide_v1=0.7825 delta=+0.39pp_CI[-0.12,+0.89]_p=0.1641 non_inferiority=pass
## 2026-11-01T01:46:14+01:00 g3_prep unigram=ok fill_rows=1076068 filled_row0_sentences=0 note=V8_is_noop_soft_filled_equals_soft v8=skipped reason=no_empty_row0_targets
## 2026-11-01T01:46:26+01:00 start gate=G3 run=v2 steps=3000 resumed=0 distill=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_lm_2m_slice100k/soft.npz distill_align=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_lm_2m_slice100k/masks.align.npz distill_mask=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_lm_2m_slice100k/masks.keep.kd.npz batch=256 ctx=40 d=256 layers=6 heads=4 ff=768 seed=0
## 2026-11-01T02:26:25+01:00 done gate=G3 run=v2 loss=5.0402 resumed=0
## 2026-11-01T02:26:30+01:00 start gate=G3 run=v3 steps=3000 resumed=0 distill=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_lm_2m_slice100k/soft.npz distill_align=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_lm_2m_slice100k/masks.align.npz distill_mask=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_lm_2m_slice100k/masks.keep.kd.npz distill_weight=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_lm_2m_slice100k/masks.masks.npz batch=256 ctx=40 d=256 layers=6 heads=4 ff=768 seed=0
## 2026-11-01T03:06:32+01:00 done gate=G3 run=v3 loss=5.0283 resumed=0
## 2026-11-01T03:08:00+01:00 gate=G3 result=failed reason=no_variant_met_threshold ref=G1_v9_3000_5.0304 v2=5.0402_delta=+0.0098 v3=5.0283_delta=-0.0021 v8=skipped_noop promoted=0
## 2026-11-01T03:08:00+01:00 gate=G4 result=blocked reason=G3_promoted_no_variant entry=G3_promoted_ge_1
## 2026-11-01T03:08:00+01:00 gate=G5 result=blocked reason=G4_not_entered
## 2026-11-01T03:08:00+01:00 gate=G6 result=blocked reason=G4_not_passed averaging=deferred
## 2026-11-01T03:08:00+01:00 gate=G7 result=blocked reason=G6_not_passed
## 2026-11-01T03:08:00+01:00 budget gpu_hours_used=15.85 cap=72 tests_run=6 all_resumed=0
## 2026-11-01T11:55:17+01:00 start gate=AUDIT run=v8fix steps=3000 resumed=0 distill=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_lm_2m_slice100k/soft_filled_fixed.npz distill_align=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_lm_2m_slice100k/masks.align.npz distill_mask=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_lm_2m_slice100k/masks.keep.kd.npz batch=256 ctx=40 d=256 layers=6 heads=4 ff=768 seed=0
## 2026-11-01T12:34:54+01:00 done gate=AUDIT run=v8fix loss=5.0335 best=5.0335 best_step=3000 resumed=0
## 2026-11-01T12:43:03+01:00 start gate=AUDIT run=tail steps=3000 resumed=0 distill=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_lm_2m_slice100k/soft_tail0938.npz distill_align=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_lm_2m_slice100k/masks.align.npz distill_mask=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_lm_2m_slice100k/masks.keep.kd.npz batch=256 ctx=40 d=256 layers=6 heads=4 ff=768 seed=0
## 2026-11-01T13:22:35+01:00 done gate=AUDIT run=tail loss=5.0551 best=5.0551 best_step=3000 resumed=0
## 2026-11-01T13:23:45+01:00 start gate=AUDIT run=share1 steps=3000 resumed=0 distill=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_lm_2m_slice100k/soft.npz distill_align=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_lm_2m_slice100k/masks.align.npz distill_mask=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_lm_2m_slice100k/masks.keep.kd.npz distill_share=1.0 batch=256 ctx=40 d=256 layers=6 heads=4 ff=768 seed=0
## 2026-11-01T14:05:17+01:00 done gate=AUDIT run=share1 loss=5.0610 best=5.0610 best_step=3000 resumed=0
## 2026-11-01T14:05:29+01:00 start gate=AUDIT run=alpha03 steps=3000 resumed=0 distill=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_lm_2m_slice100k/soft.npz distill_align=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_lm_2m_slice100k/masks.align.npz distill_mask=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_lm_2m_slice100k/masks.keep.kd.npz distill_alpha=0.3 batch=256 ctx=40 d=256 layers=6 heads=4 ff=768 seed=0
## 2026-11-01T14:45:18+01:00 done gate=AUDIT run=alpha03 loss=4.9821 best=4.9821 best_step=3000 resumed=0
## 2026-11-01T14:45:46+01:00 start gate=AUDIT run=alpha03_nomask steps=3000 resumed=0 distill=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_lm_2m_slice100k/soft.npz distill_align=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_lm_2m_slice100k/masks.align.npz distill_alpha=0.3 batch=256 ctx=40 d=256 layers=6 heads=4 ff=768 seed=0
## 2026-11-01T15:25:30+01:00 done gate=AUDIT run=alpha03_nomask loss=4.9792 best=4.9792 best_step=3000 resumed=0
## 2026-11-01T15:27:00+01:00 gate=G2 correction final=4.3087/4.1711 best=4.3023/4.1686 best_step=28500 delta_best=-0.1337 export=best.pt
## 2026-11-01T15:27:00+01:00 audit v8fix=5.0335 tail=5.0551 share1=5.0610 alpha03=4.9821 alpha03_nomask=4.9792 ref=5.0304 delta=-0.0512 report=plans/student-quality-audit.md
## 2026-11-01T15:27:00+01:00 audit findings fill_window_bug=yes paired_minus1_bug=yes typing_nonascii_skip=0.0868 g2_best_vs_final=yes keep_kdce_duplicate=yes
## 2026-11-01T15:27:00+01:00 budget gpu_hours_used=19.17 cap=72 remaining=52.83
## 2026-11-01T15:27:00+01:00 replan G5_prime alpha=0.3 30k glide_non_inferiority=required then_G6_prime_budget
## 2026-11-01T15:38:50+01:00 start gate=G5P run=alpha03 steps=30000 resumed=0 distill=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_soft_2m.npz distill_align=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_soft_2m.masks.align.npz distill_alpha=0.3 batch=256 ctx=40 d=256 layers=6 heads=4 ff=768 seed=0
## 2026-11-01T22:16:20+01:00 done gate=G5P run=alpha03 loss=4.1183 best=4.1177 best_step=28500 resumed=0
## 2026-11-01T22:18:00+01:00 gate=G5P result=passed heldout_best=4.1177 g2_best=4.1686 delta=-0.0509 glide=0.7871 vs_g2=+0.08pp_CI[-0.43,+0.58]_p=0.8804 non_inferiority=pass vs_2m=+0.23pp_CI[-0.31,+0.77]_p=0.4709 ship=no
## 2026-11-01T22:18:00+01:00 budget gpu_hours_used=25.78 cap=72 remaining=46.22
## 2026-11-01T22:18:00+01:00 next G6P 60k alpha=0.3 then_90k_if_ge_0.01 120k_over_cap
## 2026-11-01T22:18:14+01:00 start gate=G6P run=60k steps=60000 resumed=0 distill=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_soft_2m.npz distill_align=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_soft_2m.masks.align.npz distill_alpha=0.3 batch=256 ctx=40 d=256 layers=6 heads=4 ff=768 seed=0
## 2026-11-02T11:36:37+01:00 done gate=G6P run=60k loss=4.0481 best=4.0468 best_step=57500 resumed=0
## 2026-11-02T11:38:00+01:00 gate=G6P run=60k result=better best=4.0468 vs_30k=4.1177 delta=-0.0709 next=90k
## 2026-11-02T11:38:00+01:00 budget gpu_hours_used=39.07 cap=72 remaining=32.93
## 2026-11-02T11:38:00+01:00 next G6P 90k 120k_over_cap
## 2026-11-02T11:37:30+01:00 start gate=G6P run=90k steps=90000 resumed=0 distill=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_soft_2m.npz distill_align=/mnt/g/C0ding/git/wmkeyboard-wmlm/wmk-glide/artifacts/out/de_soft_2m.masks.align.npz distill_alpha=0.3 batch=256 ctx=40 d=256 layers=6 heads=4 ff=768 seed=0
## 2026-11-03T06:55:35+01:00 done gate=G6P run=90k loss=4.0077 best=4.0071 best_step=88000 resumed=0
## 2026-11-03T07:00:00+01:00 gate=G6P run=90k result=better best=4.0071 vs_60k=4.0468 delta=-0.0397 vs_2m=4.1913 ppl_delta=+0.1842 next=G7
## 2026-11-03T07:00:00+01:00 budget gpu_hours_used=58.36 cap=72 remaining=13.64
## 2026-11-03T07:00:00+01:00 gate=G7 result=failed reason=typing_strip_full_0.85_lt_1.0 per_register_mean=1.10 ship=hold
## 2026-11-03T07:00:00+01:00 audit g0_holm_combine_rank_fix no_reject_unchanged paired_g7_holm=3_reject
## 2026-11-03T07:00:00+01:00 peer student_v2_90k=not_started reason=budget_58.36_plus_19.3_gt_72_and_peer_untrusted
