import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip, BarChart, Bar, XAxis, YAxis } from 'recharts'

const NATURE_COLORS = [
  '#ff0055', '#ff00aa', '#ff00ff', '#aa00ff', '#5500ff',
  '#0055ff', '#00aaff', '#00ffff', '#00ffaa', '#00ff55',
  '#55ff00', '#aaff00', '#ffff00', '#ffaa00', '#ff5500',
  '#ff0000', '#ff5555', '#ff55aa', '#ff55ff', '#aa55ff',
  '#5555ff', '#55aaff', '#55ffff', '#55ffaa', '#55ff55'
]

function StatisticsPanel({ statistics }) {
  const formatDuration = (seconds) => {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    const secs = seconds % 60
    return `${hours}h ${minutes}m ${secs}s`
  }

  const calculateOdds = (encounters) => {
    if (encounters === 0) return '0.00%'
    const probability = (1 - Math.pow(8191/8192, encounters)) * 100
    return `${probability.toFixed(2)}%`
  }

  // Prepare nature data for chart
  const natureData = Object.entries(statistics.natures || {}).map(([name, count]) => ({
    name,
    value: count
  })).sort((a, b) => b.value - a.value).slice(0, 10)

  // Prepare gender data for chart
  const genderData = Object.entries(statistics.genders || {}).map(([name, count]) => ({
    name,
    value: count
  }))

  return (
    <div className="panel statistics-panel">
      <h2 className="panel-title">Statistics</h2>
      
      {statistics.hunt_name && (
        <div style={{
          fontSize: '0.8rem',
          color: 'var(--accent-cyan)',
          marginBottom: '1rem',
          padding: '0.4rem 0.6rem',
          background: 'rgba(0, 255, 255, 0.05)',
          borderRadius: '4px',
          borderLeft: '3px solid var(--accent-cyan)',
          fontFamily: "'Courier New', monospace"
        }}>
          {statistics.hunt_name}
        </div>
      )}
      
      <div className="stat-box holo-card">
        <div className="stat-label">Total Encounters</div>
        <div className="stat-value" style={{ fontSize: '3rem' }}>
          {statistics.encounters || 0}
        </div>
      </div>

      <div className="stat-box">
        <div className="stat-label">Shiny Probability</div>
        <div className="stat-value shiny" style={{ fontSize: '1.5rem' }}>
          {calculateOdds(statistics.encounters || 0)}
        </div>
        <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
          Base odds: 1/8192 (0.0122%)
        </div>
      </div>

      {statistics.last_encounter && (
        <div className="stat-box holo-card">
          <div className="stat-label">Last Encounter</div>
          <div style={{ marginTop: '0.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
              <span className="neon-text magenta">Gender:</span>
              <span>{statistics.last_encounter.gender || 'Unknown'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span className="neon-text magenta">Nature:</span>
              <span>{statistics.last_encounter.nature || 'Unknown'}</span>
            </div>
          </div>
        </div>
      )}

      {genderData.length > 0 && (
        <div className="chart-container">
          <div className="stat-label" style={{ marginBottom: '1rem' }}>Gender Distribution</div>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={genderData}
                cx="50%"
                cy="50%"
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
              >
                {genderData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.name === 'Male' ? '#00aaff' : '#ff0088'} />
                ))}
              </Pie>
              <Tooltip 
                contentStyle={{ 
                  background: 'var(--bg-secondary)', 
                  border: '1px solid var(--accent-cyan)',
                  borderRadius: '4px'
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}

      {natureData.length > 0 && (
        <div className="chart-container">
          <div className="stat-label" style={{ marginBottom: '1rem' }}>Top 10 Natures</div>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={natureData}>
              <XAxis 
                dataKey="name" 
                angle={-45}
                textAnchor="end"
                height={100}
                tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
              />
              <YAxis tick={{ fill: 'var(--text-secondary)' }} />
              <Tooltip 
                contentStyle={{ 
                  background: 'var(--bg-secondary)', 
                  border: '1px solid var(--accent-cyan)',
                  borderRadius: '4px'
                }}
              />
              <Bar dataKey="value" fill="var(--accent-cyan)">
                {natureData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={NATURE_COLORS[index % NATURE_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}

export default StatisticsPanel
