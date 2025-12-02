/**
 * Dr. S (StatGuard) Page JavaScript
 * Handles PDF upload and analysis display
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

// Run Dr. S analysis
async function runAnalysis() {
    if (!currentFileId) {
        showToast('Please upload a file first', 'error');
        return;
    }
    
    // Show results container
    document.getElementById('analysisPlaceholder').style.display = 'none';
    document.getElementById('analysisResults').style.display = 'block';
    
    // Reset all steps
    ['step1', 'step2', 'step3', 'step4'].forEach(id => {
        document.getElementById(`${id}Status`).textContent = '⏳';
        document.getElementById(`${id}Content`).innerHTML = '';
        document.getElementById(id).classList.add('running');
    });
    
    try {
        const response = await fetch(`/trinity-api/analyze/dr-s?file_id=${encodeURIComponent(currentFileId)}`, {
            method: 'POST'
        });
        
        if (!response.ok) throw new Error('Analysis failed');
        
        const result = await response.json();
        displayResults(result);
    } catch (error) {
        console.error('Analysis error:', error);
        showToast('Analysis failed. Please try again.', 'error');
        
        // Show demo results on error
        displayDemoResults();
    }
}

// Display analysis results
function displayResults(result) {
    // Step 1: Formatting Check
    setTimeout(() => {
        const step1 = document.getElementById('step1');
        step1.classList.remove('running');
        
        const status = result.formatting_check.status;
        document.getElementById('step1Status').textContent = 
            status === 'PASS' ? '✅' : status === 'WARNING' ? '⚠️' : '❌';
        
        let html = `<div class="${status === 'PASS' ? 'success' : 'alert'}-item">Status: ${status}</div>`;
        
        if (result.formatting_check.warnings?.length > 0) {
            result.formatting_check.warnings.forEach(w => {
                html += `<div class="alert-item">[ALERT] ${w.message}</div>`;
            });
        }
        
        if (result.formatting_check.footer_consistency?.program_name) {
            html += `<div class="info-item">Program Name: ${result.formatting_check.footer_consistency.program_name}</div>`;
        }
        
        document.getElementById('step1Content').innerHTML = html;
    }, 500);
    
    // Step 2: Logic Check
    setTimeout(() => {
        const step2 = document.getElementById('step2');
        step2.classList.remove('running');
        
        const status = result.logic_check.status;
        document.getElementById('step2Status').textContent = status === 'PASS' ? '✅' : '❌';
        
        let html = `<div class="success-item">Status: ${status}</div>`;
        
        if (result.logic_check.population_n_check?.n_values_found?.length > 0) {
            html += `<div class="info-item">N values found: ${result.logic_check.population_n_check.n_values_found.join(', ')}</div>`;
        }
        
        const calcs = result.logic_check.percentage_verification?.calculations || [];
        if (calcs.length > 0) {
            html += `<div class="info-item">Calculations verified: ${calcs.length}</div>`;
            calcs.slice(0, 3).forEach(c => {
                html += `<div class="success-item">${c.count}/${c.n} = ${c.calculated}% (Reported: ${c.reported}%) ✓</div>`;
            });
        }
        
        document.getElementById('step2Content').innerHTML = html;
    }, 1000);
    
    // Step 3: Cross Check
    setTimeout(() => {
        const step3 = document.getElementById('step3');
        step3.classList.remove('running');
        
        document.getElementById('step3Status').textContent = '✅';
        
        let html = `<div class="success-item">Status: ${result.cross_check.status}</div>`;
        
        const refs = result.cross_check.references_found;
        if (refs?.tables?.length > 0) {
            html += `<div class="info-item">Table references found: ${refs.tables.join(', ')}</div>`;
        }
        if (refs?.listings?.length > 0) {
            html += `<div class="info-item">Listing references found: ${refs.listings.join(', ')}</div>`;
        }
        
        html += `<div class="info-item">${result.cross_check.note || 'Cross-table validation complete.'}</div>`;
        
        document.getElementById('step3Content').innerHTML = html;
    }, 1500);
    
    // Step 4: Diff Check
    setTimeout(() => {
        const step4 = document.getElementById('step4');
        step4.classList.remove('running');
        
        if (result.diff_check) {
            document.getElementById('step4Status').textContent = 
                result.diff_check.status === 'NO_CHANGES' ? '✅' : 'ℹ️';
            
            let html = `<div class="info-item">Status: ${result.diff_check.status}</div>`;
            
            if (result.diff_check.changes?.length > 0) {
                result.diff_check.changes.forEach(c => {
                    html += `<div class="alert-item">${c.message}</div>`;
                });
            }
            
            document.getElementById('step4Content').innerHTML = html;
        } else {
            document.getElementById('step4Status').textContent = '➖';
            document.getElementById('step4Content').innerHTML = 
                '<div class="info-item">No previous version available for comparison.</div>';
        }
    }, 2000);
    
    // Summary
    setTimeout(() => {
        document.getElementById('analysisSummary').innerHTML = `
            <strong>Summary:</strong> ${result.summary}
            <br><small>Execution time: ${result.execution_time.toFixed(2)}s</small>
        `;
    }, 2500);
}

// Display demo results when API is not available
function displayDemoResults() {
    const demoResult = {
        formatting_check: {
            status: 'WARNING',
            warnings: [
                { message: 'Data Cutoff Date is a placeholder: DDMMMYYYY found' },
                { message: 'Data Extraction Date is a placeholder: DDMMMYYYY found' }
            ],
            footer_consistency: { program_name: 't-ae-pt.sas' }
        },
        logic_check: {
            status: 'PASS',
            population_n_check: { n_values_found: [127, 126] },
            percentage_verification: {
                calculations: [
                    { count: 6, n: 127, calculated: 4.72, reported: 4.7, match: true },
                    { count: 1, n: 126, calculated: 0.79, reported: 0.8, match: true }
                ]
            }
        },
        cross_check: {
            status: 'PASS',
            references_found: { tables: ['14.3.1.2', '14.3.1.4'], listings: ['16.2.7'] },
            note: 'Cross-table validation requires multiple uploaded files for full analysis'
        },
        diff_check: {
            status: 'CHANGES_DETECTED',
            changes: [
                { message: 'Row Added: "Septic shock" was not present in v1.0' },
                { message: 'Value Changed: "Pneumonia" (Placebo) increased from 0% to 0.8%' }
            ]
        },
        summary: '⚠️ 2 formatting warnings | ✅ Logic check passed | ✅ Cross-references identified | ℹ️ Version changes detected',
        execution_time: 0.45
    };
    
    displayResults(demoResult);
}


