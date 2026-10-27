#!/usr/bin/env Rscript

args_full <- commandArgs(trailingOnly = FALSE)
file_arg <- sub("^--file=", "", args_full[grepl("^--file=", args_full)])
root_dir <- if (length(file_arg)) dirname(normalizePath(file_arg[[1]])) else normalizePath(".")
setwd(root_dir)

python <- Sys.getenv("PYTHON", unset = "python3")
matplotlib_cache <- file.path(tempdir(), "matplotlib")
dir.create(matplotlib_cache, recursive = TRUE, showWarnings = FALSE)
Sys.setenv(MPLBACKEND = "Agg", MPLCONFIGDIR = matplotlib_cache)
embedding_status <- system2(
  python,
  c(file.path("text_embedding", "run_text_embedding.py"))
)
if (embedding_status != 0) stop("Text-embedding workflow failed.")

if (!rmarkdown::pandoc_available()) {
  candidates <- c(
    "/Applications/RStudio.app/Contents/Resources/app/quarto/bin/tools/aarch64",
    "/Applications/RStudio.app/Contents/Resources/app/quarto/bin/tools/x86_64",
    "/Applications/Positron.app/Contents/Resources/app/quarto/bin/tools/aarch64",
    "/Applications/Positron.app/Contents/Resources/app/quarto/bin/tools/x86_64"
  )
  pandoc_dir <- candidates[file.exists(file.path(candidates, "pandoc"))][1]
  if (!is.na(pandoc_dir)) Sys.setenv(RSTUDIO_PANDOC = pandoc_dir)
}

dir.create(file.path("outputs", "reports"), recursive = TRUE, showWarnings = FALSE)
analysis_env <- new.env(parent = globalenv())
rmarkdown::render(
  "Main_SI_All.Rmd",
  output_file = "Main_SI_All.html",
  output_dir = file.path("outputs", "reports"),
  quiet = TRUE,
  clean = TRUE,
  envir = analysis_env
)

# Validate each displayed fit and confidence band against its numeric-temperature model.
check_curve <- function(curve, model) {
  predictor <- names(model$model)[2]
  grid <- setNames(data.frame(curve$x), predictor)
  expected <- predict(model, grid, interval = "confidence")
  stopifnot(min(curve$x) == 1.5, max(curve$x) == 6,
            max(abs(as.matrix(curve[c("y", "ymin", "ymax")]) - expected)) < 1e-8)
}
for (pair in list(c("plot_a", "m_index"), c("plot_b", "m_p1"), c("plot_c", "m_p2"))) {
  curve <- ggplot2::ggplot_build(analysis_env[[pair[1]]])$data[[3]]
  check_curve(curve, analysis_env[[pair[2]]])
}
party_curves <- ggplot2::ggplot_build(analysis_env$plot_d)$data[[3]]
for (i in seq_along(levels(analysis_env$party_three$party_figure))) {
  party <- levels(analysis_env$party_three$party_figure)[i]
  subset <- analysis_env$party_three[analysis_env$party_three$party_figure == party, ]
  model <- lm(worry_index ~ temp_numeric_c, data = subset)
  check_curve(party_curves[party_curves$group == i, ], model)
}
message("All six fitted lines and confidence bands match numeric-temperature predictions.")
status <- system2(python, c(file.path("scripts", "sync_statistical_tables.py"), "--compile"))
if (status != 0) stop("Statistical table synchronization failed.")

report_path <- file.path("outputs", "reports", "Main_SI_All.html")
normalized_outputs <- c(
  report_path,
  list.files(file.path("outputs", "tables"), pattern = "\\.tex$", full.names = TRUE)
)
for (path in normalized_outputs) {
  lines <- readLines(path, warn = FALSE)
  writeLines(sub("[ \t]+$", "", lines), path)
}

writeLines(capture.output(sessionInfo()), file.path("validation", "sessionInfo.txt"))
source(file.path("scripts", "validate_outputs.R"), local = new.env(parent = globalenv()))
source(file.path("scripts", "write_manifest.R"), local = new.env(parent = globalenv()))
message("Complete. Open outputs/reports/Main_SI_All.html")
