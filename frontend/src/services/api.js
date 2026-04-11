import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Automation Control
export const startAutomation = () => api.post('/api/automation/start')
export const stopAutomation = () => api.post('/api/automation/stop')
export const getAutomationStatus = async () => {
  const response = await api.get('/api/automation/status')
  return response.data
}

// Statistics (now supports optional hunt_id filter)
export const getStatistics = async (huntId = null) => {
  const params = huntId ? `?hunt_id=${huntId}` : ''
  const response = await api.get(`/api/statistics/current${params}`)
  return response.data
}

export const getHistory = async (limit = 100, offset = 0, huntId = null) => {
  let url = `/api/statistics/history?limit=${limit}&offset=${offset}`
  if (huntId) url += `&hunt_id=${huntId}`
  const response = await api.get(url)
  return response.data
}

export const getCharts = async (huntId = null) => {
  const params = huntId ? `?hunt_id=${huntId}` : ''
  const response = await api.get(`/api/statistics/charts${params}`)
  return response.data
}

// Hunts
export const getHunts = async () => {
  const response = await api.get('/api/statistics/hunts')
  return response.data
}

export const resetStatistics = async () => {
  const response = await api.post('/api/statistics/reset')
  return response.data
}

// Manual Control
export const sendButtonPress = (button) => 
  api.post('/api/control/button', { button })

export const getESP32Status = async () => {
  const response = await api.get('/api/control/esp32/status')
  return response.data
}

export const getESP32Config = async () => {
  const response = await api.get('/api/control/esp32/config')
  return response.data
}

export const updateESP32Config = async (config) => {
  const response = await api.put('/api/control/esp32/config', config)
  return response.data
}

// Calibration
export const saveZone = (zoneType, coordinates) =>
  api.post('/api/calibration/zone', { zone_type: zoneType, coordinates })

export const uploadTemplate = (formData) =>
  api.post('/api/calibration/template', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })

export const getCurrentCalibration = async () => {
  const response = await api.get('/api/calibration/current')
  return response.data
}

// Configuration
export const getConfig = async () => {
  const response = await api.get('/api/config')
  return response.data
}

export const updateConfig = (config) =>
  api.put('/api/config', config)

// Camera Management
export const getCameraDevices = async () => {
  const response = await api.get('/api/camera/devices')
  return response.data
}

export const selectCamera = (index) =>
  api.post('/api/camera/select', { index })

export const saveCameraToConfig = (index) =>
  api.post('/api/camera/save-to-config', { index })

export const getCurrentCamera = async () => {
  const response = await api.get('/api/camera/current')
  return response.data
}

// Template Management
export const getTemplateStatus = async () => {
  const response = await api.get('/api/templates/status')
  return response.data
}

export const captureTemplate = async (templateKey) => {
  const response = await api.post('/api/templates/capture', { template_key: templateKey })
  return response.data
}

export const deleteTemplate = async (templateKey) => {
  const response = await api.delete(`/api/templates/${templateKey}`)
  return response.data
}

export const reloadTemplates = async () => {
  const response = await api.post('/api/templates/reload')
  return response.data
}

export const getTemplatePreviewUrl = (templateKey) =>
  `${API_BASE_URL}/api/templates/preview/${templateKey}`

export default api
