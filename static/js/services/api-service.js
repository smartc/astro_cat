/**
 * API Service - Centralized API calls for FITS Cataloger
 */

const ApiService = {
    stats: {
        getStats: () => axios.get('/api/stats')
    },

    files: {
        getFiles: (params) => axios.get('/api/files', { params }),
        getFilterOptions: () => axios.get('/api/filter-options'),
        getAllFileIds: (params) => axios.get('/api/files/ids', { params }) 
    },

    imagingSessions: {
        getAll: (params) => axios.get('/api/imaging-sessions', { params }),
        getDetails: (sessionId) => axios.get(`/api/imaging-sessions/${sessionId}/details`),
        getIds: (params) => axios.get('/api/imaging-sessions/ids', { params }),  // NEW
    },
    
    processingSessions: {
        getAll: (params) => axios.get('/api/processing-sessions', { params }),
        getById: (sessionId) => axios.get(`/api/processing-sessions/${sessionId}`),
        getIds: (params) => axios.get('/api/processing-sessions/ids', { params }),  // NEW
        create: (payload) => axios.post('/api/processing-sessions', payload),
        addFiles: (sessionId, fileIds) => 
            axios.post(`/api/processing-sessions/${sessionId}/add-files`, fileIds, {
                headers: { 'Content-Type': 'application/json' }
            }),
        updateStatus: (sessionId, payload) => 
            axios.put(`/api/processing-sessions/${sessionId}/status`, payload),
        delete: (sessionId, removeFiles = false) => 
            axios.delete(`/api/processing-sessions/${sessionId}?remove_files=${removeFiles}`),
        getCalibrationMatches: (sessionId) => 
            axios.get(`/api/processing-sessions/${sessionId}/calibration-matches`),
        removeObject: (sessionId, objectName) =>
            axios.delete(`/api/processing-sessions/${sessionId}/objects/${encodeURIComponent(objectName)}`)
    },

    operations: {
        startScan: () => axios.post('/api/operations/scan'),
        startValidate: () => axios.post('/api/operations/validate'),
        startMigrate: () => axios.post('/api/operations/migrate'),
        getStatus: (taskId) => axios.get(`/api/operations/status/${taskId}`)
    }
};

window.ApiService = ApiService;