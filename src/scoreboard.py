import urllib.request
import json

# Configurable constants
LEAGUE_ID = 42654852
SEASON_ID = 2024
TEAM_ID = 4
SLOT_ID_BENCH = 20  # Bench players have a slotId of 20

# Function to fetch data from ESPN API
def fetch_data(league_id, season_id):
    espn_api_url = (
        f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/"
        f"{season_id}/segments/0/leagues/{league_id}?view=mScoreboard&view=mRoster"
    )
    with urllib.request.urlopen(espn_api_url) as url:
        return json.loads(url.read().decode())

# Extract relevant data from the API response
def extract_scores_and_rosters(data):
    scores = []
    rosters = []

    for match in data['schedule']:
        if 'home' in match and 'away' in match:
            for side in ['home', 'away']:
                team_data = match[side]
                scores.append({
                    'matchupId': match['id'],
                    'teamId': team_data['teamId'],
                    'totalPointsLive': team_data.get('totalPointsLive', 0),
                    'totalProjectedPointsLive': team_data.get('totalProjectedPointsLive', 0)
                })

                # Extract roster information
                if 'rosterForCurrentScoringPeriod' in team_data:
                    for entry in team_data['rosterForCurrentScoringPeriod']['entries']:
                        player_info = entry['playerPoolEntry']['player']
                        rosters.append({
                            'teamId': team_data['teamId'],
                            'fullName': player_info['fullName'],
                            'proTeamId': player_info['proTeamId'],
                            'slotId': entry['lineupSlotId'],
                            'locked': entry['playerPoolEntry'].get('lineupLocked', False)
                        })

    return scores, rosters

# Calculate bonus wins and add team abbreviations
def enrich_scores(scores, data):
    median_score = sorted([team['totalProjectedPointsLive'] for team in scores])[len(scores) // 2]
    team_abbrevs = {team['id']: team['abbrev'] for team in data['teams']}

    for team in scores:
        team['bonusWin'] = team['totalProjectedPointsLive'] > median_score
        team['abbrev'] = team_abbrevs.get(team['teamId'], '')

# Count locked and unlocked players
def count_locked_players(rosters):
    locked_counts = {}
    unlocked_counts = {}

    for player in rosters:
        if player['slotId'] == SLOT_ID_BENCH:
            continue  # Skip bench players
        team_id = player['teamId']
        if team_id not in locked_counts:
            locked_counts[team_id] = 0
            unlocked_counts[team_id] = 0
        if player['locked']:
            locked_counts[team_id] += 1
        else:
            unlocked_counts[team_id] += 1

    return locked_counts, unlocked_counts

# Main function to orchestrate the data fetching and processing
def main():
    data = fetch_data(LEAGUE_ID, SEASON_ID)
    scores, rosters = extract_scores_and_rosters(data)
    enrich_scores(scores, data)

    locked_counts, unlocked_counts = count_locked_players(rosters)

    # Merge locked and unlocked player counts into the scores
    for team in scores:
        team['locked'] = locked_counts.get(team['teamId'], 0)
        team['unlocked'] = unlocked_counts.get(team['teamId'], 0)

    # Filter for the selected matchup (where TEAM_ID is present)
    selected_scores = [team for team in scores if team['matchupId'] == next(t['matchupId'] for t in scores if t['teamId'] == TEAM_ID)]

    # Ensure there are exactly two teams in the matchup
    if len(selected_scores) == 2:
        team1, team2 = selected_scores

        # Format the scoreboard with teams as columns
        scoreboard = f"""
{team1['abbrev']:<8} {team2['abbrev']:>8}
{team1['totalPointsLive']:<8.1f} {team2['totalPointsLive']:>8.1f}
{team1['totalProjectedPointsLive']:<8.1f} {team2['totalProjectedPointsLive']:>8.1f}
{str(team1['locked']) + '/' + str(team1['unlocked']):<8} {str(team2['locked']) + '/' + str(team2['unlocked']):>8}
"""
        # Display the scoreboard
        print(scoreboard.strip()) 

if __name__ == "__main__":
    main()
