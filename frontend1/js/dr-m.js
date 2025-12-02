/**
 * Dr. M (MediSense) Page JavaScript
 * Handles PDF upload and medical analysis display
 */

// PDF.js configuration
if (typeof pdfjsLib !== 'undefined') {
    pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
}

let currentFileId = null;
let currentPdfDoc = null;

// Initialize page
document.addEventListener('DOMContentLoaded', () => {
    setupFileUpload('uploadZone', 'fileInput', handleFileSelected);
    
    const runBtn = document.getElementById('runAnalysisBtn');
    if (runBtn) {
        runBtn.addEventListener('click', runAnalysis);
    }
});

// Handle file selection
async function handleFileSelected(file) {
    if (!file || file.type !== 'application/pdf') {
        showToast('Please select a PDF file', 'error');
        return;
    }
    
    // Update UI
    document.getElementById('currentFileName').textContent = file.name;
    document.getElementById('uploadZone').style.display = 'none';
    document.getElementById('pdfViewer').style.display = 'block';
    document.getElementById('runAnalysisBtn').disabled = false;
    
    // Render PDF preview
    await renderPdfPreview(file);
    
    // Upload file to backend
    await uploadFile(file);
}

// Render PDF preview
async function renderPdfPreview(file) {
    const arrayBuffer = await file.arrayBuffer();
    const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
    currentPdfDoc = pdf;
    
    const page = await pdf.getPage(1);
    const scale = 1.5;
    const viewport = page.getViewport({ scale });
    
    const canvas = document.getElementById('pdfCanvas');
    const context = canvas.getContext('2d');
    canvas.height = viewport.height;
    canvas.width = viewport.width;
    
    await page.render({
        canvasContext: context,
        viewport: viewport
    }).promise;
}

// Upload file to backend
async function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch('/trinity-api/upload', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) throw new Error('Upload failed');
        
        const data = await response.json();
        currentFileId = data.file_id;
        showToast('File uploaded successfully', 'success');
    } catch (error) {
        console.error('Upload error:', error);
        showToast('Failed to upload file', 'error');
    }
}

// Run Dr. M analysis
async function runAnalysis() {
    if (!currentFileId) {
        showToast('Please upload a file first', 'error');
        return;
    }
    
    // Show results container
    document.getElementById('analysisPlaceholder').style.display = 'none';
    document.getElementById('analysisResults').style.display = 'block';
    
    // Reset all panels
    ['panel1', 'panel2', 'panel3', 'panel4'].forEach(id => {
        document.getElementById(`${id}Status`).textContent = '⏳';
        document.getElementById(`${id}Content`).innerHTML = '';
        document.getElementById(id).classList.add('running');
    });
    
    try {
        const response = await fetch(`/trinity-api/analyze/dr-m?file_id=${encodeURIComponent(currentFileId)}`, {
            method: 'POST'
        });
        
        if (!response.ok) throw new Error('Analysis failed');
        
        const result = await response.json();
        displayResults(result);
    } catch (error) {
        console.error('Analysis error:', error);
        showToast('Analysis failed. Showing demo results.', 'error');
        
        // Show demo results on error
        displayDemoResults();
    }
}

// Display analysis results
function displayResults(result) {
    // Panel 1: Mortality Overview
    setTimeout(() => {
        const panel1 = document.getElementById('panel1');
        panel1.classList.remove('running');
        
        const status = result.mortality_overview.status;
        document.getElementById('panel1Status').textContent = 
            status === 'BALANCED' ? '✅' : '⚠️';
        
        let html = `<div class="${status === 'BALANCED' ? 'success' : 'alert'}-item">
            Status: ${status}
        </div>`;
        
        const balance = result.mortality_overview.mortality_balance;
        if (balance) {
            html += `<div class="info-item">
                <strong>Mortality Balance:</strong><br>
                Treatment: ${balance.treatment_total} deaths | Placebo: ${balance.placebo_total} deaths<br>
                ${balance.insight}
            </div>`;
        }
        
        const imbalances = result.mortality_overview.specific_imbalances || [];
        if (imbalances.length > 0) {
            html += `<div class="info-item"><strong>Specific Imbalances:</strong></div>`;
            imbalances.forEach(i => {
                html += `<div class="alert-item">
                    ${i.event}: Treatment ${i.treatment_pct}% vs Placebo ${i.placebo_pct}%
                    (${i.direction.replace(/_/g, ' ')})
                </div>`;
            });
        }
        
        if (result.mortality_overview.coding_notes) {
            html += `<div class="info-item">📝 ${result.mortality_overview.coding_notes}</div>`;
        }
        
        document.getElementById('panel1Content').innerHTML = html;
    }, 500);
    
    // Panel 2: Sentinel Events
    setTimeout(() => {
        const panel2 = document.getElementById('panel2');
        panel2.classList.remove('running');
        
        const events = result.sentinel_events || [];
        document.getElementById('panel2Status').textContent = 
            events.length === 0 ? '✅' : '🚨';
        
        let html = '';
        
        if (events.length === 0) {
            html = '<div class="success-item">No critical sentinel events detected.</div>';
        } else {
            events.forEach(event => {
                const icon = event.severity === 'critical' ? '🔴' : '🟠';
                const alertClass = event.severity === 'critical' ? 'alert' : 'info';
                
                html += `
                    <div class="${alertClass}-item">
                        <strong>${icon} ${event.severity.toUpperCase()}: ${event.keyword_matched}</strong><br>
                        <span style="color: var(--text-muted);">${event.medical_context}</span><br>
                        <span style="color: var(--teal-primary);">→ ${event.recommendation}</span>
                    </div>
                `;
            });
        }
        
        document.getElementById('panel2Content').innerHTML = html;
    }, 1200);
    
    // Panel 3: Contextual Analysis
    setTimeout(() => {
        const panel3 = document.getElementById('panel3');
        panel3.classList.remove('running');
        
        document.getElementById('panel3Status').textContent = '✅';
        
        let html = '';
        
        const demographics = result.contextual_analysis.demographics_detected || {};
        if (Object.keys(demographics).length > 0) {
            html += '<div class="info-item"><strong>Demographics Detected:</strong>';
            if (demographics.median_age) {
                html += `<br>Median Age: ${demographics.median_age} years`;
            }
            if (demographics.elderly_percent) {
                html += `<br>Age ≥ 65: ${demographics.elderly_percent}%`;
            }
            html += '</div>';
        }
        
        const insights = result.contextual_analysis.contextual_insights || [];
        insights.forEach(insight => {
            html += `
                <div class="info-item">
                    <strong>${insight.type.replace(/_/g, ' ').toUpperCase()}:</strong>
                    ${insight.event ? `<br>Event: ${insight.event}` : ''}
                    <br><span style="color: var(--text-secondary);">${insight.interpretation || insight.insight}</span>
                    ${insight.next_step ? `<br><span style="color: var(--teal-primary);">→ ${insight.next_step}</span>` : ''}
                </div>
            `;
        });
        
        if (!html) {
            html = '<div class="info-item">No specific contextual patterns identified.</div>';
        }
        
        document.getElementById('panel3Content').innerHTML = html;
    }, 1800);
    
    // Panel 4: Summary
    setTimeout(() => {
        const panel4 = document.getElementById('panel4');
        panel4.classList.remove('running');
        
        const summary = result.medical_summary;
        const riskLevel = summary.risk_level;
        
        document.getElementById('panel4Status').textContent = 
            riskLevel === 'LOW' ? '✅' : riskLevel === 'MEDIUM' ? '⚠️' : '🚨';
        
        let html = `
            <div class="${riskLevel === 'LOW' ? 'success' : riskLevel === 'MEDIUM' ? 'info' : 'alert'}-item">
                <strong>Risk Level: ${riskLevel}</strong>
            </div>
            <div class="info-item">
                <strong>Conclusion:</strong><br>
                ${summary.conclusion}
            </div>
        `;
        
        if (summary.suggested_actions?.length > 0) {
            html += '<div class="info-item"><strong>Suggested Actions:</strong></div>';
            summary.suggested_actions.forEach(action => {
                const priorityColor = action.priority === 'high' ? 'var(--red-accent)' : 
                                     action.priority === 'medium' ? 'var(--amber-primary)' : 'var(--teal-primary)';
                html += `
                    <div class="info-item" style="border-left-color: ${priorityColor};">
                        [${action.priority.toUpperCase()}] <strong>${action.action}</strong><br>
                        ${action.detail}
                    </div>
                `;
            });
        }
        
        html += `<div class="info-item" style="font-style: italic; color: var(--text-muted);">
            "${summary.closing_note}"
        </div>`;
        
        html += `<small style="color: var(--text-muted);">Execution time: ${result.execution_time.toFixed(2)}s</small>`;
        
        document.getElementById('panel4Content').innerHTML = html;
    }, 2400);
}

// Display demo results when API is not available
function displayDemoResults() {
    const demoResult = {
        mortality_overview: {
            status: 'ATTENTION_REQUIRED',
            mortality_balance: {
                treatment_total: 6,
                placebo_total: 6,
                insight: 'Overall mortality appears balanced between treatment arms.'
            },
            specific_imbalances: [
                { event: 'Death (unspecified)', treatment_pct: 1.6, placebo_pct: 0, direction: 'higher_in_treatment' },
                { event: 'Pneumonia', treatment_pct: 0, placebo_pct: 0.8, direction: 'higher_in_placebo' }
            ],
            coding_notes: 'PT "Death" appears in treatment arm but not placebo. This likely indicates "Unspecified Death" coding, not excess mortality.',
            pattern_analysis: {
                treatment_drivers: ['Acquired tracheo-oesophageal fistula', 'Myocarditis', 'Brain injury'],
                placebo_drivers: ['Pneumonia', 'Septic shock']
            }
        },
        sentinel_events: [
            {
                type: 'fistula',
                keyword_matched: 'Acquired Tracheo-oesophageal Fistula',
                severity: 'critical',
                color: 'red',
                medical_context: 'Rare, life-threatening event. In oncology, often associated with VEGF inhibitors or concurrent radiation therapy.',
                recommendation: 'Immediate Patient Profile review required. Check: Did this patient receive thoracic radiation? Is the tumor invading the esophagus?'
            },
            {
                type: 'myocarditis',
                keyword_matched: 'Myocarditis',
                severity: 'critical',
                color: 'red',
                medical_context: 'Known immune-related Adverse Event (irAE) for checkpoint inhibitors.',
                recommendation: 'Check if death occurred early in treatment. Verify Troponin levels in listing.'
            }
        ],
        contextual_analysis: {
            demographics_detected: {
                median_age: 76.0,
                elderly_percent: 86.6
            },
            contextual_insights: [
                {
                    type: 'fall_risk',
                    event: 'Brain injury',
                    interpretation: 'Given the advanced age of the population (median 76 years), "Brain injury" leading to death is highly likely secondary to a Fall.',
                    next_step: 'Check AE Listing for preceding events: Dizziness, Syncope, Hypotension'
                }
            ]
        },
        medical_summary: {
            conclusion: 'No overall mortality imbalance detected. However, the safety profile shows distinct signals: Fistula and Myocarditis in the treatment arm warrant specific risk management language in the CSR.',
            risk_level: 'HIGH',
            suggested_actions: [
                {
                    priority: 'high',
                    action: 'Narrative Writing',
                    detail: 'Prioritize drafting narratives for Subject ID associated with the Fistula and Myocarditis events.'
                },
                {
                    priority: 'medium',
                    action: 'Protocol Check',
                    detail: 'Verify if Fistula is a known risk in the Investigator\'s Brochure (IB).'
                },
                {
                    priority: 'low',
                    action: 'Data Cleaning',
                    detail: 'Query the "Brain injury" case to confirm if a fall was involved.'
                }
            ],
            closing_note: 'While Dr. S ensures your data is correct, Dr. M ensures your data is understood.'
        },
        execution_time: 0.67
    };
    
    displayResults(demoResult);
}


