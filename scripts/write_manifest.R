#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)
root_dir <- if (length(args) >= 1) normalizePath(args[[1]], mustWork = TRUE) else normalizePath(".")

files <- list.files(root_dir, recursive = TRUE, full.names = TRUE, all.files = TRUE)
files <- files[file.info(files)$isdir %in% FALSE]
relative <- sub(paste0("^", root_dir, "/"), "", files)
keep <- !grepl("^(tmp/|\\.git/|MANIFEST\\.md5$)", relative)
keep <- keep & !grepl("^validation/(package_check\\.txt|results_check\\.csv|privacy_audit\\.csv)$", relative)
keep <- keep & !grepl("_stargazer\\.tex$|\\.(aux|out|log|fls|fdb_latexmk|pyc)$|__pycache__/", relative)
files <- files[keep]
relative <- relative[keep]

hashes <- unname(tools::md5sum(files))
manifest <- data.frame(md5 = hashes, file = relative)
manifest <- manifest[order(manifest$file), ]
write.table(
  manifest,
  file.path(root_dir, "MANIFEST.md5"),
  row.names = FALSE,
  col.names = FALSE,
  quote = FALSE,
  sep = "  "
)
