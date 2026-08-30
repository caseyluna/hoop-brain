#!/usr/bin/env Rscript
#
# Generic hoopR/wehoop invocation utility (CAL-252).
#
# Usage: Rscript run.R <function_name> <json_args> <output_path_prefix>
#
#   function_name       fully-qualified, e.g. "hoopR::espn_nba_injuries" or
#                        "wehoop::wnba_teamplayeronoffsummary"
#   json_args           JSON object of named args, e.g. '{"season": 2026}'
#   output_path_prefix  where to write CSV output. A function that returns a
#                        single data frame writes "<prefix>.csv". A function
#                        that returns a named list of data frames (several
#                        hoopR/wehoop stats-API wrappers do - e.g. on/off
#                        summary returns Overall/PlayersOn/PlayersOff) writes
#                        one file per element: "<prefix>__<name>.csv".

suppressPackageStartupMessages({
  library(jsonlite)
  library(readr)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 3) {
  stop("usage: run.R <function_name> <json_args> <output_path_prefix>")
}
function_name <- args[[1]]
json_args <- args[[2]]
output_prefix <- args[[3]]

parts <- strsplit(function_name, "::", fixed = TRUE)[[1]]
if (length(parts) != 2 || !(parts[[1]] %in% c("hoopR", "wehoop"))) {
  stop(sprintf(
    "function_name must be namespaced as hoopR::<fn> or wehoop::<fn>, got: %s",
    function_name
  ))
}
pkg <- parts[[1]]
fn_name <- parts[[2]]

fn <- tryCatch(
  getExportedValue(pkg, fn_name),
  error = function(e) {
    stop(sprintf("%s::%s is not an exported function: %s", pkg, fn_name, conditionMessage(e)))
  }
)

call_args <- fromJSON(json_args, simplifyVector = TRUE)
if (!is.list(call_args)) call_args <- list()

result <- do.call(fn, call_args)

write_one <- function(df, path) {
  if (!is.data.frame(df)) {
    stop(sprintf("expected a data frame, got class: %s", paste(class(df), collapse = ", ")))
  }
  write_csv(df, path)
  message(sprintf("wrote %d rows, %d cols -> %s", nrow(df), ncol(df), path))
}

if (is.data.frame(result)) {
  write_one(result, paste0(output_prefix, ".csv"))
} else if (is.list(result)) {
  if (is.null(names(result)) || any(names(result) == "")) {
    stop("function returned an unnamed list - can't derive output filenames, adjust run.R for this function's shape")
  }
  for (part_name in names(result)) {
    write_one(result[[part_name]], sprintf("%s__%s.csv", output_prefix, part_name))
  }
} else {
  stop(sprintf("unsupported return type: %s", paste(class(result), collapse = ", ")))
}
