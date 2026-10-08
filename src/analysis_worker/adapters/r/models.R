# Linear and linear mixed models for the analysis worker.
# Called through rpy2 by analysis_worker.adapters.r.models.
# Requires lme4, lmerTest, emmeans, car and pbkrtest (for Kenward-Roger).

suppressPackageStartupMessages({
  library(lme4)
  library(lmerTest)
  library(emmeans)
  library(car)
})

# Fit a model and return its ANOVA table, variance components and diagnostics.
#   ss_type: 2 or 3; type 3 uses sum-to-zero contrasts for unordered factors
#   ddf: "Satterthwaite" or "Kenward-Roger", for mixed models
fit_anova <- function(data, formula, mixed, ss_type, ddf) {
  if (ss_type == 3) {
    options(contrasts = c("contr.sum", "contr.poly"))
  } else {
    options(contrasts = c("contr.treatment", "contr.poly"))
  }
  f <- as.formula(formula)
  warnings <- character(0)
  collect <- function(w) {
    warnings <<- c(warnings, conditionMessage(w))
    invokeRestart("muffleWarning")
  }

  if (mixed) {
    model <- withCallingHandlers(lmerTest::lmer(f, data = data, REML = TRUE), warning = collect)
    table <- as.data.frame(anova(model, type = ss_type, ddf = ddf))
    table <- data.frame(
      term = rownames(table),
      df = table[["NumDF"]],
      den_df = table[["DenDF"]],
      ss = table[["Sum Sq"]],
      ms = table[["Mean Sq"]],
      f = table[["F value"]],
      p = table[["Pr(>F)"]],
      stringsAsFactors = FALSE
    )
    vc <- as.data.frame(VarCorr(model))
    vc <- vc[vc$grp != "Residual" & is.na(vc$var2), ]
    random <- data.frame(
      group = vc$grp,
      slope = ifelse(vc$var1 == "(Intercept)", NA_character_, vc$var1),
      variance = vc$vcov,
      sd = vc$sdcor,
      stringsAsFactors = FALSE
    )
    convergence <- model@optinfo$conv$lme4$messages
    if (!is.null(convergence)) warnings <- c(warnings, convergence)
    if (isSingular(model)) warnings <- c(warnings, "The fit is singular: some variance components are estimated as zero")
    residual <- data.frame(df = NA_real_, ss = NA_real_, ms = NA_real_)
  } else {
    model <- withCallingHandlers(lm(f, data = data), warning = collect)
    if (df.residual(model) < 1) stop("The model has no residual degrees of freedom")
    raw <- as.data.frame(car::Anova(model, type = ss_type))
    raw$term <- rownames(raw)
    res <- raw[raw$term == "Residuals", ]
    raw <- raw[!(raw$term %in% c("Residuals", "(Intercept)")), ]
    table <- data.frame(
      term = raw$term,
      df = raw[["Df"]],
      den_df = NA_real_,
      ss = raw[["Sum Sq"]],
      ms = raw[["Sum Sq"]] / raw[["Df"]],
      f = raw[["F value"]],
      p = raw[["Pr(>F)"]],
      stringsAsFactors = FALSE
    )
    random <- data.frame(group = character(0), slope = character(0), variance = numeric(0), sd = numeric(0))
    residual <- data.frame(df = res[["Df"]], ss = res[["Sum Sq"]], ms = res[["Sum Sq"]] / res[["Df"]])
  }
  list(model = model, table = table, random = random, residual = residual, warnings = unique(warnings))
}

# Estimated marginal means and contrasts.
#   specs, by: column names; by may be empty
#   contrast: "pairwise", "trt.vs.ctrl" or "none"; ref: 1-based index of the control level
#   adjust: "tukey", "bonferroni", "holm", "sidak" or "none"
estimated_means <- function(model, specs, by, contrast, ref, adjust, level, ddf) {
  emm_options(lmer.df = tolower(ddf))
  by_arg <- if (length(by) == 0) NULL else by
  emm <- emmeans(model, specs = specs, by = by_arg, level = level)
  means <- as.data.frame(summary(emm, level = level))
  contrasts <- NULL
  if (contrast != "none") {
    args <- list(emm, method = contrast, adjust = adjust)
    if (contrast == "trt.vs.ctrl") args$ref <- ref
    con <- do.call(emmeans::contrast, args)
    contrasts <- as.data.frame(summary(con, infer = c(TRUE, TRUE), level = level))
  }
  list(means = means, contrasts = contrasts)
}
