from flask import Flask, render_template_string, request, jsonify
import json
import pandas as pd
import io
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

with open('mustermann_benchmarks.json', 'r') as f:
    BENCHMARKS = json.load(f)

POSITION_MAP = {
    'GK': 'GK',
    'CB': 'DEF', 'LB': 'DEF', 'RB': 'DEF', 'WB': 'DEF',
    'DM': 'MID', 'CM': 'MID', 'AM': 'MID', 'LM': 'MID', 'RM': 'MID',
    'W': 'FWD', 'ST': 'FWD', 'SS': 'FWD'
}

class MustermannAnalyzer:
    def __init__(self, benchmarks):
        self.benchmarks = benchmarks
    
    def get_position_group(self, pos):
        return POSITION_MAP.get(pos.upper(), 'MID')
    
    def calculate_rating(self, value, percentiles):
        if value >= percentiles.get('80th', float('inf')):
            return 'Elite', 80
        elif value >= percentiles.get('60th', float('inf')):
            return 'Good', 60
        elif value >= percentiles.get('40th', float('inf')):
            return 'Average', 40
        elif value >= percentiles.get('20th', float('inf')):
            return 'Poor', 20
        else:
            return 'Abysmal', 10
    
    def analyze_player(self, player_data):
        pos_group = self.get_position_group(player_data.get('Position', 'MID'))
        pos_benchmarks = self.benchmarks.get(pos_group, {})
        
        analysis = {
            'name': player_data.get('Player Name', '?'),
            'position': player_data.get('Position', '?'),
            'position_group': pos_group,
            'age': player_data.get('Age', '?'),
            'minutes': player_data.get('Minutes', 0),
            'areas': {}
        }
        
        for area, metrics in pos_benchmarks.items():
            area_scores = []
            area_data = {'ratings': {}, 'scores': {}}
            
            for metric, percentiles in metrics.items():
                col_names = [metric.upper(), metric.replace('_', ' ').upper(), metric.replace('_', ' '), metric]
                
                value = None
                for col in col_names:
                    if col in player_data:
                        value = player_data[col]
                        break
                
                if value is not None:
                    try:
                        value = float(str(value).strip('%'))
                    except:
                        continue
                    
                    rating, score = self.calculate_rating(value, percentiles)
                    area_data['ratings'][metric] = rating
                    area_data['scores'][metric] = score
                    area_scores.append(score)
            
            if area_scores:
                area_data['average_score'] = sum(area_scores) / len(area_scores)
                analysis['areas'][area] = area_data
        
        all_scores = []
        for area in analysis['areas'].values():
            if 'average_score' in area:
                all_scores.append(area['average_score'])
        
        analysis['overall_score'] = sum(all_scores) / len(all_scores) if all_scores else 0
        analysis['overall_rating'] = self._score_to_rating(analysis['overall_score'])
        
        return analysis
    
    def _score_to_rating(self, score):
        if score >= 80:
            return 'Elite'
        elif score >= 60:
            return 'Good'
        elif score >= 40:
            return 'Average'
        elif score >= 20:
            return 'Poor'
        else:
            return 'Abysmal'

analyzer = MustermannAnalyzer(BENCHMARKS)

SAMPLE_SCOUTS = [
    {'name': 'Nelson Bazetch', 'pos': 'ST', 'goals_90': 0.90, 'value': 24, 'score': 95},
    {'name': 'Tora Leah', 'pos': 'ST', 'goals_90': 0.76, 'value': 8, 'score': 92},
    {'name': 'Mohamed Sylla', 'pos': 'CB', 'pass_pct': 82, 'value': 5, 'score': 90},
]

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-PT">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Moneyball FM26</title>
<style>
body{margin:0;padding:0;font-family:Segoe UI,Tahoma,Geneva,sans-serif;background:linear-gradient(135deg,#0f0c29 0%,#302b63 50%,#24243e 100%);color:#fff;min-height:100vh}.header{background:linear-gradient(90deg,#667eea 0%,#764ba2 100%);padding:30px 20px;text-align:center}.header h1{font-size:2.5em;margin:0 0 5px 0}.container{max-width:1400px;margin:0 auto;padding:20px}.tabs{display:flex;gap:10px;margin-bottom:20px;border-bottom:2px solid rgba(255,255,255,0.1);flex-wrap:wrap}.tab-btn{padding:12px 24px;background:rgba(255,255,255,0.1);border:none;color:#fff;cursor:pointer;border-radius:5px 5px 0 0;font-size:1em;transition:all 0.3s ease}.tab-btn:hover{background:rgba(255,255,255,0.2)}.tab-btn.active{background:linear-gradient(90deg,#667eea
<div class="tabs"><button class="tab-btn active" onclick="showTab('upload')">📁 UPLOAD</button><button class="tab-btn" onclick="showTab('analyse')">📊 ANÁLISE</button><button class="tab-btn" onclick="showTab('scout')">🏆 SCOUT</button></div>
<div id="upload" class="tab-content active"><div class="upload-zone" id="uploadZone"><h3>📁 Arraste ou clique para carregar ficheiro</h3><p>CSV, PNG, JPG</p><input type="file" id="fileInput" accept=".csv,.png,.jpg,.jpeg"></div><button class="btn" onclick="processFile()">🔄 PROCESSAR</button><div id="message"></div></div>
<div id="analyse" class="tab-content"><h2>📊 Análise Moneyball</h2><div class="message info">✅ Dashboard Pronto! Processe um ficheiro CSV.</div><div class="results" id="results"></div></div>
<div id="scout" class="tab-content"><h2>🏆 Scout Search</h2><div id="scoutList"></div></div>
</div>
<script>
const uploadZone=document.getElementById('uploadZone');const fileInput=document.getElementById('fileInput');uploadZone.addEventListener('click',()=>fileInput.click());uploadZone.addEventListener('dragover',(e)=>{e.preventDefault();uploadZone.classList.add('dragover')});uploadZone.addEventListener('dragleave',()=>{uploadZone.classList.remove('dragover')});uploadZone.addEventListener('drop',(e)=>{e.preventDefault();uploadZone.classList.remove('dragover');fileInput.files=e.dataTransfer.files});function showTab(t){document.querySelectorAll('.tab-content').forEach(e=>e.classList.remove('active'));document.querySelectorAll('.tab-btn').forEach(e=>e.classList.remove('active'));document.getElementById(t).classList.add('active');event.target.classList.add('active')}function processFile(){const f=fileInput.files[0];if(!f){showMessage('info','❌ Seleccione um ficheiro!');return}const d=new FormData();d.append('file',f);fetch('/process',{method:'POST',body:d}).then(r=>r.json()).then(d=>{if(d.success){showMessage('info','✅ Ficheiro processado!');showAnalysis(d)}else{showMessage('info','❌ Erro: '+d.error)}}).catch(e=>showMessage('info','❌ Erro: '+e))}function showAnalysis(d){const r=document.getElementById('results');r.innerHTML='';if(!d.players||d.players.length===0){r.innerHTML='<div class="message">Sem dados</div>';return}d.players.forEach(p=>{const c=document.createElement('div');c.className='player-card';const s=Math.min(100,p.overall_score);c.innerHTML=`<div class="player-header"><div><div class="player-name">${p.name}</div><div>${p.position} - Age: ${p.age}</div></div><span class="rating-badge rating-${p.overall_rating.toLowerCase()}">${p.overall_rating}</span></div><div style="margin-bottom:15px"><div style="display:flex;justify-content:space-between;margin-bottom:5px"><strong>Score</strong><strong>${p.overall_score.toFixed(1)}/100</strong></div><div class="score-bar"><div class="score-fill" style="width:${s}%"></div></div></div>`;r.appendChild(c)});showTab('analyse')}function showMessage(t,x){const m=document.getElementById('message');m.className='message '+t;m.textContent=x}function loadScouts(){fetch('/scouts').then(r=>r.json()).then(d=>{const s=document.getElementById('scoutList');s.innerHTML='';d.scouts.forEach(c=>{const card=document.createElement('div');card.innerHTML=`<div class="player-card"><strong>${c.name}</strong><p>${c.pos} - €${c.value}M - Score: ${c.score}</p></div>`;s.appendChild(card)})})}loadScouts();
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/process', methods=['POST'])
def process():
    try:
        file = request.files['file']
        if not file:
            return jsonify({'success': False, 'error': 'Sem ficheiro'})
        
        filename = secure_filename(file.filename)
        
        if filename.endswith('.csv'):
            stream = io.StringIO(file.stream.read().decode('UTF-8'))
            df = pd.read_csv(stream)
        else:
            return jsonify({'success': False, 'error': 'Apenas CSV suportado'})
        
        players = []
        for idx, row in df.iterrows():
            player_dict = row.to_dict()
            analysis = analyzer.analyze_player(player_dict)
            players.append(analysis)
        
        players.sort(key=lambda x: x['overall_score'], reverse=True)
        
        return jsonify({'success': True, 'players': players, 'total': len(players)})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/scouts')
def scouts():
    return jsonify({'scouts': SAMPLE_SCOUTS})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
