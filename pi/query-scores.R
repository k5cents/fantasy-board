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

json_file <- "/home/kiernan/Developer/scoreboard/scoreboard.json"

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

s <- s |>
  # filter rows without projected points
  filter(!is.na(proj_points)) |>
  # add supplemental columns
  mutate(
    # round points
    live_points = round(live_points, 0),
    proj_points = round(proj_points, 0),
    # flag if projected score is in top half
    bonus_win = proj_points > median(proj_points),
    # rank of projected score out of all scores
    score_rank = min_rank(desc(proj_points)),
    # team abbreviation
    team_abbrev = dat$teams$abbrev[match(team_id, dat$teams$id)]
  ) |>
  # keep only the selected matchup
  filter(matchup_id == matchup_id[param_team == team_id]) |>
  # rename and select columns
  select(team_id, team_abbrev, live_points, proj_points, score_rank)

# add player status -------------------------------------------------------

# find the players starting on each team
rosters <- dat$teams$roster$entries[dat$teams$id %in% s$team_id]
out <- rep(list(NA), length(rosters))
for (i in seq_along(rosters)) {
  out[[i]] <- tibble(
    team_id = rosters[[i]]$playerPoolEntry$onTeamId,
    full_name = rosters[[i]]$playerPoolEntry$player$fullName,
    proj_team = rosters[[i]]$playerPoolEntry$player$proTeamId,
    slot_id = rosters[[i]]$lineupSlotId,
    is_locked = rosters[[i]]$playerPoolEntry$lineupLocked
  )
}

# combine the players into a single list
out <- do.call("rbind", out)

# limit data frame to players not on bench (20)
out <- out[out$slot_id != 20 & out$slot_id != 21, ]

# count the players yet to start on each team
n_locked <- by(out$is_locked, out$team_id, sum)
n_unlocked <- by(!out$is_locked, out$team_id, sum)

locked <- tibble(
  team_id = names(n_locked),
  n_locked = as.vector(n_locked),
  n_unlocked = as.vector(n_unlocked)
)

s <- merge(s, locked)

out <- list(
  status = "ok",
  league = param_league,
  season = param_season,
  timestamp = Sys.time(),
  scoreboard = s
)

# write to json -----------------------------------------------------------

write_json(
  x = out,
  path = json_file,
  pretty = TRUE
)
