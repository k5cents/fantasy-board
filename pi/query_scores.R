# Format live ESPN fantasy football scores from API and save as JSON
# https://github.com/k5cents/fantasy-board
# Kiernan Nicholls

suppressPackageStartupMessages({
  library(dplyr)
  library(httr2)
  library(tibble)
  library(jsonlite)
})

# config ------------------------------------------------------------------

# set parameters for league and team
param_league <- 252353
param_season <- 2024
param_team <- 6

os <- Sys.info()["sysname"]

json_file <- "scoreboard.json"

# request -----------------------------------------------------------------

# build a HTTR request to pull scores from API
req <- request("https://lm-api-reads.fantasy.espn.com")

req <- req |>
  req_url_path_append("apis/v3/games/ffl") |>
  req_url_path_append("seasons", param_season) |>
  req_url_path_append("segments", 0) |>
  req_url_path_append("leagues", param_league) |>
  req_url_query(view = "mScoreboard", view = "mRoster") |>
  req_user_agent("https://github.com/k5cents/fflr/") |>
  req_headers("Accept" = "application/json") |>
  req_retry(max_tries = 3)

resp <- tryCatch(req_perform(req), error = function(e) NULL)

# if there was an R or HTTP error then write simple message to file
if (is.null(resp) || resp_is_error(resp)) {
  error <- list(
    status = "http-error",
    http_code = resp_status(resp),
    timestamp = Sys.time()
  )
  write_json(error, json_file, pretty = TRUE)
  quit(save = "no", status = 0)
}

# note the time of the HTTP response
resp_time <- as.POSIXct(
  x = resp$headers$date,
  format = "%a, %d %b %Y %H:%M:%S GMT", 
  tz = "GMT"
)

resp_time <- format(resp_time, tz = "America/New_York")

# pull the data from the response
dat <- resp_body_json(resp, simplifyVector = TRUE)

# format ------------------------------------------------------------------

period_id <- dat$scoringPeriodId

# build data frame from home and away sub-tables
s <- tibble(
  matchup_period = dat$status$currentMatchupPeriod,
  matchup_id = c(
    dat$schedule$id,
    dat$schedule$id
  ),
  team_id = c(
    dat$schedule$home$teamId,
    dat$schedule$away$teamId
  ),
  live_points = c(
    dat$schedule$home$totalPointsLive,
    dat$schedule$away$totalPointsLive
  ),
  proj_points = c(
    dat$schedule$home$totalProjectedPointsLive,
    dat$schedule$away$totalProjectedPointsLive
  )
)

# if there are zero rows write simple error
if (nrow(s) == 0) {
  error <- list(
    status = "row-projections",
    timestamp = Sys.time()
  )
  write_json(error, json_file, pretty = TRUE)
  quit(save = "no", status = 0)
}

proj_fifth <- sort(s$proj_points[!is.na(s$proj_points)], decreasing = TRUE)[5]

s <- s |>
  # filter rows without projected points
  filter(
    !is.na(proj_points)
  ) |>
  # add supplemental columns
  mutate(
    # round points
    live_points = round(live_points, 1),
    proj_points = round(proj_points, 1),
    # flag if projected score is in top half
    bonus_win = as.integer(proj_points >= proj_fifth),
    bonus_diff = round(proj_points - proj_fifth, 1),
    # rank of projected score out of all scores
    score_rank = min_rank(desc(proj_points)),
    # team abbreviation
    team_abbrev = dat$teams$abbrev[match(team_id, dat$teams$id)]
  ) |>
  # flag if projected to win match
  mutate(
    match_win = as.integer(proj_points == max(proj_points)), 
    .by = matchup_id
  ) |>
  # keep only the selected matchup
  filter(
    matchup_id == matchup_id[param_team == team_id]
  )

# record ------------------------------------------------------------------

wins <- tibble(
  team_abbrev = dat$teams$abbrev,
  current_wins = dat$teams$record$overall$wins
)

s <- left_join(s, wins, by = "team_abbrev")

# write to json -----------------------------------------------------------

out <- list(
  status = "ok",
  league = param_league,
  season = param_season,
  week = dat$scoringPeriodId,
  timestamp = resp_time,
  scoreboard = s
)

toJSON(out, pretty = TRUE)

# write_json(
#   x = out,
#   path = json_file,
#   pretty = TRUE
# )
