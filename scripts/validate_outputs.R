#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
})

args <- commandArgs(trailingOnly = TRUE)
root_dir <- if (length(args) >= 1) normalizePath(args[[1]], mustWork = TRUE) else normalizePath(".")

read_qualtrics <- function(path) {
  read_csv(path, show_col_types = FALSE, progress = FALSE) |> slice(-c(1, 2))
}

v1_raw <- read_qualtrics(file.path(root_dir, "data/validation1/validation1.csv"))
v1_pre_speed <- v1_raw |>
  filter(Finished == "TRUE", QID2 == "I agree", QID6 == "Somewhat disagree") |>
  mutate(`Duration (in seconds)` = as.numeric(`Duration (in seconds)`))
speed_threshold <- median(v1_pre_speed$`Duration (in seconds)`, na.rm = TRUE) / 3
v1 <- v1_pre_speed |>
  filter(`Duration (in seconds)` >= speed_threshold) |>
  mutate(
    across(c(QID5_1, Q17_1, Q18_1, temp_c), as.numeric),
    worry_index = (QID5_1 + Q17_1 + Q18_1) / 3,
    temp_numeric_c = temp_c
  ) |>
  tidyr::drop_na(QID5_1, Q17_1, Q18_1, worry_index, temp_numeric_c, partyid)

p1 <- read_qualtrics(file.path(root_dir, "data/pilot1/pilot1_full500data.csv")) |>
  filter(Finished == "TRUE", QID6 == "Somewhat disagree") |>
  transmute(worry = abs(parse_number(QID5)), temp_numeric = as.numeric(temp_c)) |>
  tidyr::drop_na()

p2 <- read_qualtrics(file.path(root_dir, "data/pilot2/pilot2_wave2.csv")) |>
  filter(Finished %in% c("TRUE", "True"), QID6 == "Somewhat disagree") |>
  transmute(worry = as.numeric(QID5_1), temp_numeric = as.numeric(temp_c)) |>
  tidyr::drop_na()

party_binary <- v1 |>
  mutate(
    party = case_when(
      partyid == "Democrat" ~ "Democrat",
      partyid == "Republican" ~ "Republican",
      partyid %in% c("Independent", "No preference", "Other party") &
        leaning == "Closer to Democratic" ~ "Democrat",
      partyid %in% c("Independent", "No preference", "Other party") &
        leaning == "Closer to Republican" ~ "Republican",
      TRUE ~ NA_character_
    ),
    party = factor(party, levels = c("Democrat", "Republican"))
  ) |>
  tidyr::drop_na(party)

party_three <- v1 |>
  mutate(
    party = case_when(
      partyid == "Democrat" | leaning == "Closer to Democratic" ~ "Democrat",
      partyid == "Republican" | leaning == "Closer to Republican" ~ "Republican",
      TRUE ~ "Independent / Other"
    ),
    party = factor(party, levels = c("Democrat", "Republican", "Independent / Other"))
  )

alpha_cronbach <- function(mat) {
  k <- ncol(mat)
  (k / (k - 1)) * (1 - sum(apply(mat, 2, var)) / var(rowSums(mat)))
}

m_main <- lm(worry_index ~ temp_numeric_c, data = v1)
m_p1 <- lm(worry ~ temp_numeric, data = p1)
m_p2 <- lm(worry ~ temp_numeric, data = p2)
m_party <- lm(worry_index ~ temp_numeric_c * party, data = party_binary)
v1_unit_centered <- v1 |>
  mutate(temp_centered_c = temp_numeric_c - mean(temp_numeric_c))
m_unit_centered <- lm(
  worry_index ~ temp_centered_c * factor(unit),
  data = v1_unit_centered
)

s13 <- read_csv(
  file.path(root_dir, "outputs/tables/table_s13.csv"),
  show_col_types = FALSE
)
s13_regression <- s13 |> filter(panel == "A")
s13_embedding <- s13 |> filter(panel == "B")

s13_embedding_expected <- tribble(
  ~model, ~input, ~full_estimate, ~full_p, ~exclusion_estimate, ~exclusion_p,
  "MPNet-Base", "Raw", 0.002233583516782822, 0.024975024975024976, 0.0019471485961043, 0.0519480519480519,
  "MPNet-Base", "Clean", 0.002331558366839126, 0.017982017982017984, 0.0020200571820154, 0.0529470529470529,
  "MiniLM-L6", "Raw", 0.001325971746956145, 0.10989010989010989, 0.0010225923982283, 0.2467532467532467,
  "MiniLM-L6", "Clean", 0.0013125550493031102, 0.12287712287712288, 0.0010327317505686, 0.2617382617382617,
  "E5-Large", "Raw", 0.00013930800879813354, 0.5804195804195804, 0.00005559784715891691, 0.8261738261738262,
  "E5-Large", "Clean", 0.00004060935617289374, 0.8601398601398601, -0.00004851824736198298, 0.8601398601398601,
  "BGE-Large", "Raw", 0.001108956764033664, 0.04095904095904096, 0.00091978767772, 0.0759240759240759,
  "BGE-Large", "Clean", 0.0009500770442716355, 0.07592407592407592, 0.0007637967505861, 0.1458541458541458,
  "Mxbai-Large", "Raw", 0.000947876932045677, 0.1018981018981019, 0.0007278910998901, 0.1978021978021978,
  "Mxbai-Large", "Clean", 0.0008065611193183164, 0.15884115884115885, 0.0005902769986239, 0.3126873126873127
)

s13_embedding_comparison <- s13_embedding |>
  select(model, input, full_estimate, full_p, exclusion_estimate, exclusion_p) |>
  inner_join(
    s13_embedding_expected,
    by = c("model", "input"),
    suffix = c("_actual", "_expected")
  )
s13_embedding_max_error <- max(abs(unlist(
  s13_embedding_comparison |>
    transmute(
      full_estimate = full_estimate_actual - full_estimate_expected,
      full_p = full_p_actual - full_p_expected,
      exclusion_estimate = exclusion_estimate_actual - exclusion_estimate_expected,
      exclusion_p = exclusion_p_actual - exclusion_p_expected
    )
)))

actual_values <- c(
  main_n = nrow(v1),
  pilot1_n = nrow(p1),
  pilot2_n = nrow(p2),
  text_n = {
    text <- v1_raw |>
      filter(Finished == "TRUE", QID2 == "I agree", QID6 == "Somewhat disagree") |>
      mutate(`Duration (in seconds)` = as.numeric(`Duration (in seconds)`)) |>
      filter(`Duration (in seconds)` >= speed_threshold) |>
      tidyr::drop_na(Q23, temp_c)
    nrow(text)
  },
  alpha = alpha_cronbach(as.matrix(v1[, c("QID5_1", "Q17_1", "Q18_1")])),
  main_slope = unname(coef(m_main)[["temp_numeric_c"]]),
  main_p = summary(m_main)$coefficients["temp_numeric_c", "Pr(>|t|)"],
  pilot1_slope = unname(coef(m_p1)[["temp_numeric"]]),
  pilot1_p = summary(m_p1)$coefficients["temp_numeric", "Pr(>|t|)"],
  pilot2_slope = unname(coef(m_p2)[["temp_numeric"]]),
  pilot2_p = summary(m_p2)$coefficients["temp_numeric", "Pr(>|t|)"],
  party_binary_n = nrow(party_binary),
  party_three_n = nrow(party_three),
  party_democrat_n = sum(party_three$party == "Democrat"),
  party_republican_n = sum(party_three$party == "Republican"),
  party_independent_other_n = sum(party_three$party == "Independent / Other"),
  party_interaction_p = summary(m_party)$coefficients[
    "temp_numeric_c:partyRepublican", "Pr(>|t|)"
  ],
  unit_fixed_effect = unname(coef(m_unit_centered)[["factor(unit)F"]]),
  unit_fixed_effect_p = summary(m_unit_centered)$coefficients[
    "factor(unit)F", "Pr(>|t|)"
  ],
  unit_interaction = unname(coef(m_unit_centered)[["temp_centered_c:factor(unit)F"]]),
  unit_interaction_p = summary(m_unit_centered)$coefficients[
    "temp_centered_c:factor(unit)F", "Pr(>|t|)"
  ],
  s13_rows = nrow(s13),
  s13_regression_rows = nrow(s13_regression),
  s13_embedding_rows = nrow(s13_embedding),
  s13_full_n = s13_regression$full_N[[1]],
  s13_exclusion_n = s13_regression$exclusion_N[[1]],
  s13_full_slope = s13_regression$full_estimate[[1]],
  s13_exclusion_slope = s13_regression$exclusion_estimate[[1]],
  s13_exclusion_p = s13_regression$exclusion_p[[1]],
  s13_embedding_max_error = s13_embedding_max_error
)

expected_values <- c(
  main_n = 986,
  pilot1_n = 493,
  pilot2_n = 498,
  text_n = 986,
  alpha = 0.9187399217099776,
  main_slope = 2.7669488796412374,
  main_p = 1.0501760722178428e-05,
  pilot1_slope = 0.1262443,
  pilot1_p = 0.02560655,
  pilot2_slope = 1.5114922774374921,
  pilot2_p = 0.11070390954025182,
  party_binary_n = 845,
  party_three_n = 986,
  party_democrat_n = 491,
  party_republican_n = 354,
  party_independent_other_n = 141,
  party_interaction_p = 0.938,
  unit_fixed_effect = 4.27409957486069,
  unit_fixed_effect_p = 0.0168833908905454,
  unit_interaction = -0.711850892925401,
  unit_interaction_p = 0.568282848966837,
  s13_rows = 11,
  s13_regression_rows = 1,
  s13_embedding_rows = 10,
  s13_full_n = 986,
  s13_exclusion_n = 967,
  s13_full_slope = 2.7669488796412374,
  s13_exclusion_slope = 2.862818,
  s13_exclusion_p = 0.000006860367,
  s13_embedding_max_error = 0
)

tolerances <- c(
  main_n = 0, pilot1_n = 0, pilot2_n = 0, text_n = 0,
  alpha = 1e-6, main_slope = 1e-6, main_p = 1e-10,
  pilot1_slope = 1e-6, pilot1_p = 1e-8,
  pilot2_slope = 1e-6, pilot2_p = 1e-7,
  party_binary_n = 0, party_three_n = 0,
  party_democrat_n = 0, party_republican_n = 0, party_independent_other_n = 0,
  party_interaction_p = 5e-4,
  unit_fixed_effect = 1e-10, unit_fixed_effect_p = 1e-10,
  unit_interaction = 1e-10, unit_interaction_p = 1e-10,
  s13_rows = 0, s13_regression_rows = 0, s13_embedding_rows = 0,
  s13_full_n = 0, s13_exclusion_n = 0,
  s13_full_slope = 1e-12, s13_exclusion_slope = 1e-12,
  s13_exclusion_p = 1e-12, s13_embedding_max_error = 1e-12
)

checks <- tibble(
  check = names(expected_values),
  expected = unname(expected_values),
  actual = unname(actual_values),
  tolerance = unname(tolerances[names(expected_values)]),
  passed = abs(actual_values - expected_values) <= tolerances
)

forbidden <- c(
  "StartDate", "EndDate", "RecordedDate", "IPAddress", "ResponseId",
  "RecipientLastName", "RecipientFirstName", "RecipientEmail",
  "ExternalReference", "LocationLatitude", "LocationLongitude", "PROLIFIC_PID", "Q16"
)
public_files <- file.path(
  root_dir,
  c(
    "data/pilot1/pilot1_full500data.csv",
    "data/pilot2/pilot2_wave2.csv",
    "data/validation1/validation1.csv",
    "outputs/tables/table_s13.csv"
  )
)
privacy_ok <- all(vapply(public_files, function(path) {
  nms <- names(read_csv(path, n_max = 0, show_col_types = FALSE))
  !any(forbidden %in% nms)
}, logical(1)))

identifier_patterns <- c(
  email = "[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}",
  ipv4 = "\\b(?:[0-9]{1,3}\\.){3}[0-9]{1,3}\\b",
  prolific_like = "\\b[0-9a-fA-F]{24}\\b"
)
content_privacy_ok <- all(vapply(public_files, function(path) {
  dat <- read_csv(
    path,
    col_types = cols(.default = col_character()),
    show_col_types = FALSE
  )
  values <- unlist(dat, use.names = FALSE)
  values <- values[!is.na(values)]
  !any(vapply(identifier_patterns, function(pattern) {
    any(grepl(pattern, values, perl = TRUE))
  }, logical(1)))
}, logical(1)))

required_outputs <- file.path(
  root_dir,
  c(
    "outputs/figures/Figure1.pdf",
    "outputs/figures/Figure2.png",
    "outputs/tables/table_s1.csv",
    "outputs/tables/table_s2.csv",
    "outputs/tables/table_s3.csv",
    "outputs/tables/table_s4.csv",
    "outputs/tables/table_s5.csv",
    "outputs/tables/table_s6.csv",
    "outputs/tables/table_s7.csv",
    "outputs/tables/table_s8.csv",
    "outputs/tables/table_s9.csv",
    "outputs/tables/table_s10.csv",
    "outputs/tables/table_s11.csv",
    "outputs/tables/table_s12.csv",
    "outputs/tables/table_s13.csv",
    "outputs/reports/Main_SI_All.html"
  )
)
outputs_ok <- all(file.exists(required_outputs))

table_paths <- file.path(
  root_dir,
  "outputs",
  "tables",
  paste0("table_s", 1:13, ".csv")
)
table_columns <- lapply(table_paths, function(path) {
  names(read_csv(path, n_max = 0, show_col_types = FALSE))
})
expected_first_columns <- c(
  "Study", "term", "term", "term", "term", "term", "term",
  "Group1", "Party", "term", "term", "Model", "panel"
)
table_numbering_ok <- identical(
  vapply(table_columns, `[[`, character(1), 1),
  expected_first_columns
)

dir.create(file.path(root_dir, "validation"), recursive = TRUE, showWarnings = FALSE)
write_csv(checks, file.path(root_dir, "validation", "results_check.csv"))
writeLines(
  c(
    paste("Participant identifier columns absent:", privacy_ok),
    paste("Participant identifier-like values absent:", content_privacy_ok),
    paste("All required outputs present:", outputs_ok),
    paste("CSV table schemas match expected outputs:", table_numbering_ok)
  ),
  file.path(root_dir, "validation", "package_check.txt")
)

if (!all(checks$passed) || !privacy_ok || !content_privacy_ok || !outputs_ok || !table_numbering_ok) {
  print(checks)
  stop("Validation failed. See validation/results_check.csv and validation/package_check.txt")
}

message("All statistical, privacy, and output checks passed.")
