#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
})

args <- commandArgs(trailingOnly = TRUE)
root_dir <- if (length(args) >= 1) normalizePath(args[[1]], mustWork = TRUE) else normalizePath(".")
source_root <- if (length(args) >= 2) normalizePath(args[[2]], mustWork = TRUE) else root_dir

relative_files <- c(
  "data/pilot1/pilot1_full500data.csv",
  "data/pilot2/pilot2_wave2.csv",
  "data/validation1/validation1.csv"
)

# Direct identifiers and unnecessary quasi-identifying collection metadata.
remove_columns <- c(
  "StartDate", "EndDate", "RecordedDate",
  "IPAddress", "ResponseId",
  "RecipientLastName", "RecipientFirstName", "RecipientEmail",
  "ExternalReference",
  "LocationLatitude", "LocationLongitude",
  "PROLIFIC_PID",
  # Qualtrics duplicated the Prolific ID into this survey field.
  "Q16"
)

audit_rows <- list()

for (relative_path in relative_files) {
  source_path <- file.path(source_root, relative_path)
  output_path <- file.path(root_dir, relative_path)
  if (!file.exists(source_path)) stop("Missing data file: ", source_path)

  dat <- read_csv(
    source_path,
    col_types = cols(.default = col_character()),
    show_col_types = FALSE,
    progress = FALSE
  )
  file_remove_columns <- remove_columns
  if (grepl("data/pilot[12]/", relative_path)) {
    # QID2 is not used by either pilot analysis and contains an email-like entry.
    file_remove_columns <- c(file_remove_columns, "QID2")
  }
  present <- intersect(file_remove_columns, names(dat))
  sanitized <- dat |> select(-any_of(file_remove_columns))
  write_csv(sanitized, output_path, na = "")

  audit_rows[[length(audit_rows) + 1]] <- tibble(
    file = relative_path,
    rows = nrow(sanitized),
    columns_before = ncol(dat),
    columns_after = ncol(sanitized),
    removed_columns = paste(present, collapse = "; ")
  )
}

dir.create(file.path(root_dir, "validation"), recursive = TRUE, showWarnings = FALSE)
write_csv(bind_rows(audit_rows), file.path(root_dir, "validation", "privacy_audit.csv"))
message("Sanitized ", length(relative_files), " datasets. Audit: validation/privacy_audit.csv")
