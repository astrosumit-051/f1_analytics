# Run from the project root. Raw inputs are never written by this project.
f1_config <- function() list(
  data_root = Sys.getenv("F1_DATA_ROOT", "F1_Pit_Wall_2018_2026"),
  seed = 355L, trials = 10000L, lookback = 5L,
  train_end = 2023L, validation_year = 2024L, test_start = 2025L,
  timing_tolerance_sec = 0.1, weather_max_age_sec = 120,
  min_pit_cycles = 10L, min_pit_races = 3L,
  min_transition_cycles = 5L, min_transition_races = 2L,
  close_margin_sec = 0.5, traffic_loss_sec = 0.5,
  traffic_gap_sec = 1.5, box_service_sec = 3,
  # Explicit scheduled-distance assumptions, NOT inferred from final results.
  # Unknown circuits are unsupported; shortened races require manual revision.
  scheduled_laps = c(albert_park=58, bahrain=57, shanghai=56, baku=51,
    catalunya=66, monaco=78, villeneuve=70, ricard=53, red_bull_ring=71,
    silverstone=52, hockenheimring=67, hungaroring=70, spa=44, monza=53,
    marina_bay=61, suzuka=53, sochi=53, americas=56, rodriguez=71,
    interlagos=71, yas_marina=55, mugello=59, nurburgring=60, portimao=66,
    imola=63, istanbul=58, jeddah=50, zandvoort=72, losail=57,
    miami=57, vegas=50))
