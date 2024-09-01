import urllib.request
import json
from config import config

class FantasyApiOnFireException(Exception):
    pass

class FantasyApi:
    def __init__(self):
        pass

    def fetch_data(self, retry_attempt=0):
        try:
            print('Fetching data from ESPN API...')
            espn_api_url = config['espn_api_url']
            with urllib.request.urlopen(espn_api_url) as url:
                data = json.loads(url.read().decode())
            print('Data successfully received from ESPN API.')
            return data
        except Exception as e:
            print(e)
            if retry_attempt < config['api_retries']:
                print('Failed to connect to API. Reattempting...')
                return self.fetch_data(retry_attempt + 1)
            else:
                raise FantasyApiOnFireException()

    def extract_scores_and_rosters(self, data):
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

    def enrich_scores(self, scores, data):
        median_score = sorted([team['totalProjectedPointsLive'] for team in scores])[len(scores) // 2]
        team_abbrevs = {team['id']: team['abbrev'] for team in data['teams']}

        for team in scores:
            team['bonusWin'] = team['totalProjectedPointsLive'] > median_score
            team['abbrev'] = team_abbrevs.get(team['teamId'], '')

    def count_locked_players(self, rosters):
        locked_counts = {}
        unlocked_counts = {}

        for player in rosters:
            if player['slotId'] == config['slot_id_bench']:
                continue
            team_id = player['teamId']
            if team_id not in locked_counts:
                locked_counts[team_id] = 0
                unlocked_counts[team_id] = 0
            if player['locked']:
                locked_counts[team_id] += 1
            else:
                unlocked_counts[team_id] += 1

        return locked_counts, unlocked_counts

    def determine_color(self, team1_score, team2_score):
        # Green for higher score, red for lower score
        if team1_score > team2_score:
            return 0x00FF00, 0xFF0000  # Green for team1, Red for team2
        elif team1_score < team2_score:
            return 0xFF0000, 0x00FF00  # Red for team1, Green for team2
        else:
            return 0xFFFF00, 0xFFFF00  # Yellow if scores are tied

    def main(self):
        data = self.fetch_data()
        scores, rosters = self.extract_scores_and_rosters(data)
        self.enrich_scores(scores, data)

        locked_counts, unlocked_counts = self.count_locked_players(rosters)

        for team in scores:
            team['locked'] = locked_counts.get(team['teamId'], 0)
            team['unlocked'] = unlocked_counts.get(team['teamId'], 0)

        selected_scores = [team for team in scores if team['matchupId'] == next(t['matchupId'] for t in scores if t['teamId'] == config['team_id'])]

        if len(selected_scores) == 2:
            team1, team2 = selected_scores

            # Determine colors based on live scores and projected scores
            live_score_color1, live_score_color2 = self.determine_color(team1['totalPointsLive'], team2['totalPointsLive'])
            projected_score_color1, projected_score_color2 = self.determine_color(team1['totalProjectedPointsLive'], team2['totalProjectedPointsLive'])

            # Grouped data for Team 1 and Team 2
            team1_group = [
                {
                    'abbrev': team1['abbrev'],
                    'live': f"{team1['totalPointsLive']:.1f}",
                    'proj': f"{team1['totalProjectedPointsLive']:.1f}",
                    'live_color': live_score_color1,
                    'proj_color': projected_score_color1,
                    'locked': f"{team1['locked']}/{team1['unlocked']}"
                }
            ]

            team2_group = [
                {
                    'abbrev': team2['abbrev'],
                    'live': f"{team2['totalPointsLive']:.1f}",
                    'proj': f"{team2['totalProjectedPointsLive']:.1f}",
                    'live_color': live_score_color2,
                    'proj_color': projected_score_color2,
                    'locked': f"{team2['locked']}/{team2['unlocked']}"
                }
            ]

            # Returning data as two separate groups
            return team1_group, team2_group

if __name__ == "__main__":
    api = FantasyApi()
    team1_group, team2_group = api.main()
    print(team1_group)
    print(team2_group)
