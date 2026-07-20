// API Base URL
const API_BASE = 'http://localhost:8000/api';

// Tab Navigation
document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const tabName = btn.dataset.tab;
        
        // Hide all tabs
        document.querySelectorAll('.tab-content').forEach(tab => {
            tab.classList.remove('active');
        });
        
        // Deactivate all buttons
        document.querySelectorAll('.nav-btn').forEach(b => {
            b.classList.remove('active');
        });
        
        // Show selected tab
        document.getElementById(tabName).classList.add('active');
        btn.classList.add('active');
    });
});

// Show/Hide Loading
function showLoading() {
    document.getElementById('loading').classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loading').classList.add('hidden');
}

// Display JSON Results
function displayJSON(elementId, data) {
    const element = document.getElementById(elementId);
    element.textContent = JSON.stringify(data, null, 2);
}

// Display Results
function displayResult(resultBoxId, contentId, data) {
    const resultBox = document.getElementById(resultBoxId);
    const content = document.getElementById(contentId);
    
    content.textContent = JSON.stringify(data, null, 2);
    resultBox.classList.remove('hidden');
}

// Copy to Clipboard
function copyToClipboard(elementId) {
    const element = document.getElementById(elementId);
    const text = element.textContent || element.innerText;
    
    navigator.clipboard.writeText(text).then(() => {
        alert('✅ Copiado para a área de transferência!');
    }).catch(err => {
        alert('❌ Erro ao copiar: ' + err);
    });
}

// 1. Analyze Resume
async function analyzeResume() {
    const resumeText = document.getElementById('resume-text').value.trim();
    
    if (!resumeText) {
        alert('⚠️ Por favor, cole seu currículo');
        return;
    }
    
    showLoading();
    
    try {
        const response = await fetch(`${API_BASE}/analyze-resume`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ resume_text: resumeText })
        });
        
        if (!response.ok) throw new Error('Erro na requisição');
        
        const data = await response.json();
        displayResult('resume-result', 'resume-content', data.profile);
    } catch (error) {
        alert('❌ Erro: ' + error.message);
    } finally {
        hideLoading();
    }
}

// 2. Search Jobs
async function searchJobs() {
    const skillsText = document.getElementById('skills').value.trim();
    const experience = parseInt(document.getElementById('experience').value);
    const keywords = document.getElementById('keywords').value.trim();
    const location = document.getElementById('location').value.trim() || null;
    const remote = document.getElementById('remote').checked;
    const topN = parseInt(document.getElementById('top-n').value);
    
    if (!keywords) {
        alert('⚠️ Por favor, digite palavras-chave para buscar');
        return;
    }
    
    const skills = skillsText.split(',').map(s => s.trim()).filter(s => s);
    const keywordsList = keywords.split(',').map(k => k.trim()).filter(k => k);
    
    const candidateProfile = {
        skills: skills,
        years_experience: experience
    };
    
    showLoading();
    
    try {
        const response = await fetch(`${API_BASE}/find-jobs`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                candidate_profile: candidateProfile,
                keywords: keywordsList,
                location: location,
                remote: remote,
                top_n: topN
            })
        });
        
        if (!response.ok) throw new Error('Erro na requisição');
        
        const data = await response.json();
        displayResult('jobs-result', 'jobs-content', data);
    } catch (error) {
        alert('❌ Erro: ' + error.message);
    } finally {
        hideLoading();
    }
}

// 3. Prepare Interview
async function prepareInterview() {
    const jobInfoText = document.getElementById('job-info').value.trim();
    const candidateInfoText = document.getElementById('candidate-info-interview').value.trim();
    
    if (!jobInfoText || !candidateInfoText) {
        alert('⚠️ Por favor, preencha ambos os campos com JSON válido');
        return;
    }
    
    try {
        const jobInfo = JSON.parse(jobInfoText);
        const candidateInfo = JSON.parse(candidateInfoText);
        
        showLoading();
        
        const response = await fetch(`${API_BASE}/prepare-interview`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                job_info: jobInfo,
                candidate_info: candidateInfo
            })
        });
        
        if (!response.ok) throw new Error('Erro na requisição');
        
        const data = await response.json();
        displayResult('interview-result', 'interview-content', data.preparation);
    } catch (error) {
        alert('❌ Erro: ' + error.message);
    } finally {
        hideLoading();
    }
}

// 4. Generate Cover Letter
async function generateCoverLetter() {
    const candidateInfoText = document.getElementById('candidate-info-letter').value.trim();
    const jobInfoText = document.getElementById('job-info-letter').value.trim();
    
    if (!candidateInfoText || !jobInfoText) {
        alert('⚠️ Por favor, preencha ambos os campos com JSON válido');
        return;
    }
    
    try {
        const candidateInfo = JSON.parse(candidateInfoText);
        const jobInfo = JSON.parse(jobInfoText);
        
        showLoading();
        
        const response = await fetch(`${API_BASE}/generate-cover-letter`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                candidate_info: candidateInfo,
                job_info: jobInfo
            })
        });
        
        if (!response.ok) throw new Error('Erro na requisição');
        
        const data = await response.json();
        
        // For cover letter, display as formatted text
        const letterContent = document.getElementById('letter-content');
        letterContent.innerHTML = data.cover_letter.replace(/\n/g, '<br>');
        document.getElementById('letter-result').classList.remove('hidden');
    } catch (error) {
        alert('❌ Erro: ' + error.message);
    } finally {
        hideLoading();
    }
}

// Check API Health on load
window.addEventListener('load', async () => {
    try {
        const response = await fetch(`${API_BASE}/health`);
        if (response.ok) {
            console.log('✅ API conectada com sucesso!');
        }
    } catch (error) {
        console.warn('⚠️ API não está acessível. Certifique-se de que o servidor está rodando em http://localhost:8000');
    }
});
