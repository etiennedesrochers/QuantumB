// Global configuration loaded from JSON / API
let compressorConfig = null;

// Compressor library, loaded from the server (/api/compressors)
let compressorsCache = [];

// Workbook selection rows, loaded from the Excel-backed API
let workbookCompressorRows = [];

// Generator workbook selection state
let workbookGeneratorFilters = null;
let workbookGeneratedCircuits = [];

function getAllTemplateNames() {
    // Only include "regular" templates (templates/templates folder).
    const regularTemplates = (compressorConfig && compressorConfig.templateTypes && compressorConfig.templateTypes.regular) || [];
    return Array.from(new Set(regularTemplates)).sort((a, b) => String(a).localeCompare(String(b)));
}

function populateTemplateSelect() {
    const templateSelect = document.getElementById('templateName');
    if (!templateSelect) return;

    const templates = getAllTemplateNames();
    templateSelect.innerHTML = '<option value="">-- Choose template --</option>';

    templates.forEach(templateName => {
        const option = document.createElement('option');
        option.value = templateName;
        option.textContent = templateName;
        templateSelect.appendChild(option);
    });
}

// Load configuration: manufacturers/applications from the static JSON file,
// template lists live from disk via the API (source of truth for template pickers)
async function loadConfiguration() {
    try {
        const response = await fetch('compressor_config.json');
        compressorConfig = await response.json();
    } catch (error) {
        console.error('Error loading configuration:', error);
        // Use default config if file fails to load
        compressorConfig = {
            manufacturers: ["Copeland", "Mitsubishi", "Schneider"],
            applications: ["ASHP-CU", "WSHP-CU", "AWHP-2P", "AWHP-4P"],
            templateTypes: {}
        };
    }

    try {
        const templatesResponse = await fetch('/api/templates');
        compressorConfig.templateTypes = await templatesResponse.json();
    } catch (error) {
        console.error('Error loading templates from API:', error);
    }

    console.log('Configuration loaded:', compressorConfig);
}

// Fetch the compressor library from the server and refresh the local cache
async function fetchCompressors() {
    try {
        const response = await fetch('/api/compressors');
        compressorsCache = await response.json();
    } catch (error) {
        console.error('Error fetching compressors:', error);
        compressorsCache = [];
    }
    return compressorsCache;
}

// Sync all compressors from workbook rows into the compressor library.
async function syncCompressorsFromWorkbook() {
    try {
        const response = await fetch('/api/compressors/sync-workbook', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.error || response.statusText);
        }

        const result = await response.json();
        compressorsCache = result.compressors || [];
        return result;
    } catch (error) {
        console.error('Error syncing compressors from workbook:', error);
        await fetchCompressors();
        return null;
    }
}

// Fetch workbook compressor rows from the Excel-backed API and refresh any
// workbook-driven controls on the page.
async function fetchWorkbookCompressors() {
    try {
        const response = await fetch('/api/workbook/compressors');
        workbookCompressorRows = await response.json();
    } catch (error) {
        console.error('Error fetching workbook compressors:', error);
        workbookCompressorRows = [];
    }

    populateWorkbookCompressorSelect();
    displayWorkbookCompressors();
    return workbookCompressorRows;
}

function populateWorkbookCompressorSelect() {
    const select = document.getElementById('workbookCompressorRow');
    if (!select) return;

    select.innerHTML = '<option value="">-- Choose workbook row --</option>';
    workbookCompressorRows.forEach((row, index) => {
        const labelParts = [
            row.nominal_capacity != null ? `${row.nominal_capacity} kW` : 'Capacity N/A',
            row.manufacturer || 'Manufacturer N/A',
            row.skid_model_number || 'Model N/A'
        ];
        const option = document.createElement('option');
        option.value = String(index);
        option.textContent = labelParts.join(' | ');
        select.appendChild(option);
    });
}

function displayWorkbookCompressors() {
    const container = document.getElementById('workbookRowsTable');
    if (!container) return;

    if (workbookCompressorRows.length === 0) {
        container.innerHTML = '<p style="color: #999; text-align: center; padding: 12px; margin: 0;">No workbook rows loaded</p>';
        return;
    }

    const rowsHtml = workbookCompressorRows.map((row, index) => `
        <tr>
            <td style="padding: 8px; border-bottom: 1px solid #eee;">${index + 1}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eee;">${row.nominal_capacity ?? ''}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eee;">${row.manufacturer ?? ''}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eee;">${row.control ?? ''}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eee;">${row.skid_model_number ?? ''}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eee;">${row.models_by_voltage?.['400v'] ?? ''}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eee;">${row.compressor_qty ?? ''}</td>
        </tr>
    `).join('');

    container.innerHTML = `
        <div style="overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                <thead>
                    <tr style="background: #f5f5f5; text-align: left;">
                        <th style="padding: 8px; border-bottom: 1px solid #ddd;">#</th>
                        <th style="padding: 8px; border-bottom: 1px solid #ddd;">Capacity</th>
                        <th style="padding: 8px; border-bottom: 1px solid #ddd;">Manufacturer</th>
                        <th style="padding: 8px; border-bottom: 1px solid #ddd;">Control</th>
                        <th style="padding: 8px; border-bottom: 1px solid #ddd;">Skid Model</th>
                        <th style="padding: 8px; border-bottom: 1px solid #ddd;">400V Model</th>
                        <th style="padding: 8px; border-bottom: 1px solid #ddd;">Qty</th>
                    </tr>
                </thead>
                <tbody>${rowsHtml}</tbody>
            </table>
        </div>
    `;
}

function loadWorkbookRowIntoForm() {
    const select = document.getElementById('workbookCompressorRow');
    if (!select) return;

    const index = parseInt(select.value, 10);
    if (Number.isNaN(index) || !workbookCompressorRows[index]) return;

    const row = workbookCompressorRows[index];
    const nameField = document.getElementById('compressorName');
    const modelField = document.getElementById('compressorModel');
    const manufacturerField = document.getElementById('compressorManufacturer');
    const capacityField = document.getElementById('compressorCapacity');

    if (nameField) nameField.value = row.skid_model_number || `${row.manufacturer || 'Compressor'} ${row.nominal_capacity || ''}`.trim();
    if (modelField) modelField.value = row.models_by_voltage?.['400v'] || row.models_by_voltage?.['200v'] || row.skid_model_number || '';
    if (manufacturerField) manufacturerField.value = row.manufacturer || '';
    if (capacityField) capacityField.value = row.nominal_capacity ?? '';
}

function getCompressorOptions() {
    return compressorsCache.map(c => c.name);
}

function inferTemplateType(templateName) {
    const templateTypes = (compressorConfig && compressorConfig.templateTypes) || {};
    for (const [category, names] of Object.entries(templateTypes)) {
        if (Array.isArray(names) && names.includes(templateName)) {
            return category;
        }
    }
    return 'regular';
}

function createTemplateId() {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') {
        return window.crypto.randomUUID();
    }
    return `tpl-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function generateCircuits() {
    const count = parseInt(document.getElementById('circuitCount').value);
    
    if (isNaN(count) || count < 1 || count > 20) {
        //alert('Please enter a valid number between 1 and 20');
        return;
    }
    
    const circuitsList = document.getElementById('circuitsList');
    circuitsList.innerHTML = '';
    
    for (let i = 1; i <= count; i++) {
        const circuitDiv = document.createElement('div');
        circuitDiv.className = 'circuit-section';
        circuitDiv.innerHTML = `
            <div class="circuit-header">
                <div class="circuit-number">${i}</div>
                <div class="circuit-name">Circuit ${i}</div>
            </div>
            <div class="circuit-content">
                <div class="circuit-compressor">
                    <div class="form-group">
                        <div class="form-field">
                            <label for="compressorchoice${i}">Circuit Compressor :</label>
                            <select id="compressorchoice${i}" name="compressorchoice${i}">
                                <option value="">Select a compressor</option>
                            </select>
                        </div>
                        <div class="form-field">
                            <label for="quantity${i}">Quantity :</label>
                            <input type="number" id="quantity${i}" name="quantity${i}" min="1" value="1">
                        </div>
                    </div>
                    <div class="form-group">
                        <div class="form-field">
                            <label for="manu${i}">Manufacturer :</label>
                            <select id="manu${i}" name="manu${i}">
                                <option value="copeland">Copeland</option>
                                <option value="mitsubishi">Mitsubishi</option>
                                <option value="schneider">Schneider</option>
                            </select>
                        </div>
                    </div> 
                </div>
            </div>
        `;
        circuitsList.appendChild(circuitDiv);
        
        // Populate compressor options from localStorage or defaults
        const selectElement = document.getElementById(`compressorchoice${i}`);
        const options = getCompressorOptions();
        options.forEach(option => {
            const optionElement = document.createElement('option');
            optionElement.value = option;
            optionElement.textContent = option;
            selectElement.appendChild(optionElement);
        });
    }
    
    document.getElementById('circuitsContainer').classList.add('active');
}


async function initGeneratorFromWorkbook() {
    const capacitySelect = document.getElementById('workbookCapacity');
    const manufacturerSelect = document.getElementById('workbookManufacturer');
    if (!capacitySelect || !manufacturerSelect) return;

    try {
        const response = await fetch('/api/workbook/generator-filters');
        workbookGeneratorFilters = await response.json();
    } catch (error) {
        console.error('Error loading generator workbook filters:', error);
        workbookGeneratorFilters = { capacities: [], manufacturers: [], tensions: [] };
    }

    const manufacturers = (workbookGeneratorFilters && workbookGeneratorFilters.manufacturers) || [];

    capacitySelect.innerHTML = '<option value="">Select a manufacturer first</option>';

    manufacturerSelect.innerHTML = '<option value="">-- Choose manufacturer --</option>';
    manufacturers.forEach(manufacturer => {
        const option = document.createElement('option');
        option.value = manufacturer;
        option.textContent = manufacturer;
        manufacturerSelect.appendChild(option);
    });
}


async function refreshCapacitiesForManufacturer() {
    const capacitySelect = document.getElementById('workbookCapacity');
    const manufacturer = document.getElementById('workbookManufacturer')?.value;
    if (!capacitySelect) return;

    if (!manufacturer) {
        capacitySelect.innerHTML = '<option value="">Select a manufacturer first</option>';
        return;
    }

    try {
        const query = new URLSearchParams({ manufacturer: manufacturer });
        const response = await fetch(`/api/workbook/generator-filters?${query.toString()}`);
        const data = await response.json();
        const capacities = data.capacities || [];

        capacitySelect.innerHTML = '<option value="">-- Choose nominal capacity (tons) --</option>';
        capacities.forEach(capacity => {
            const option = document.createElement('option');
            option.value = String(capacity);
            option.textContent = `${capacity} tons`;
            capacitySelect.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading capacities for manufacturer:', error);
        capacitySelect.innerHTML = '<option value="">Failed to load capacities</option>';
    }
}


function renderWorkbookCircuits(circuits) {
    const circuitsList = document.getElementById('circuitsList');
    const container = document.getElementById('circuitsContainer');
    if (!circuitsList || !container) return;

    if (!circuits || circuits.length === 0) {
        circuitsList.innerHTML = '<p style="color: #999; text-align: center; padding: 16px;">No circuits found for this selection.</p>';
        container.classList.add('active');
        return;
    }

    let html = '';
    circuits.forEach((circuit, index) => {
        const compressorRows = (circuit.compressors || []).map(comp => {
            return `
                <div style="padding: 8px 0; border-top: 1px solid #ececec;">
                    <div style="font-weight: 600;">${comp.skid_model_number || comp.description || comp.model_number}</div>
                    <div style="font-size: 13px; color: #666;">Model (${(document.getElementById('voltage')?.value || '')}V): ${comp.model_number || '-'}</div>
                    <div style="font-size: 13px; color: #666;">Qty: ${comp.quantity || 1}</div>
                </div>
            `;
        }).join('');

        html += `
            <div class="circuit-section">
                <div class="circuit-header">
                    <div class="circuit-number">${index + 1}</div>
                    <div class="circuit-name">${circuit.name || `Circuit ${index + 1}`}</div>
                </div>
                <div class="circuit-content" style="padding: 12px;">
                    <div style="margin-bottom: 8px; color: #444;">${circuit.description || ''}</div>
                    ${compressorRows}
                </div>
            </div>
        `;
    });

    circuitsList.innerHTML = html;
    container.classList.add('active');
}


async function loadCircuitsFromWorkbookSelection() {
    const capacity = document.getElementById('workbookCapacity')?.value;
    const manufacturer = document.getElementById('workbookManufacturer')?.value;
    const tension = document.getElementById('voltage')?.value;

    if (!capacity || !manufacturer || !tension) {
        alert('Please select manufacturer, nominal capacity (tons), and tension.');
        return;
    }

    const query = new URLSearchParams({
        capacity: String(capacity),
        manufacturer: String(manufacturer),
        tension: String(tension),
    });

    try {
        const response = await fetch(`/api/workbook/circuits?${query.toString()}`);
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            alert('Error loading circuits: ' + (err.error || response.statusText));
            return;
        }

        const payload = await response.json();
        workbookGeneratedCircuits = payload.circuits || [];
        renderWorkbookCircuits(workbookGeneratedCircuits);
    } catch (error) {
        alert('Error loading circuits: ' + error.message);
        console.error('Workbook circuit load error:', error);
    }
}

window.loadCircuitsFromWorkbookSelection = loadCircuitsFromWorkbookSelection;


// Handle Fan Manufacturer enable/disable based on Application selection
function updateFanManufacturerState() {
    const application = document.getElementById('application').value;
    const fanManufacturerField = document.getElementById('fanmanufacturer');
    
    // Applications that require fan manufacturer selection
    const applicationsWithFans = ['ASHP-CU', 'WSHP-CU', 'AWHP-2P', 'AWHP-4P'];
    
    // Enable if application needs a fan, disable otherwise (for Boiler types)
    fanManufacturerField.disabled = !applicationsWithFans.includes(application);
}

// Dark Mode Toggle
function initDarkMode() {
    const darkModeCheckbox = document.getElementById('darkModeCheckbox');
    if (!darkModeCheckbox) return;
    
    // Check localStorage for dark mode preference
    const isDarkMode = localStorage.getItem('darkMode') === 'true';
    if (isDarkMode) {
        document.documentElement.classList.add('dark-mode');
        darkModeCheckbox.checked = true;
    }
    
    darkModeCheckbox.addEventListener('change', toggleDarkMode);
}

function toggleDarkMode(event) {
    const html = document.documentElement;
    const isDarkMode = event.target.checked;
    
    if (isDarkMode) {
        html.classList.add('dark-mode');
    } else {
        html.classList.remove('dark-mode');
    }
    
    localStorage.setItem('darkMode', isDarkMode);
}

// Add event listener to form submission
document.addEventListener('DOMContentLoaded', async function() {
    // Load configuration (manufacturers/applications + live template lists)
    // and the shared compressor library before rendering anything that
    // depends on them.
    await loadConfiguration();
    await fetchCompressors();
    await fetchWorkbookCompressors();
    
    // Initialize dark mode
    initDarkMode();
    
    // Set active navbar link based on current page
    const currentPage = window.location.pathname.split('/').pop() || 'base.html';
    const navLinks = document.querySelectorAll('.navbar-link');
    navLinks.forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('href') === currentPage || 
            (currentPage === '' && link.getAttribute('href') === 'base.html')) {
            link.classList.add('active');
        }
    });
    
    const form = document.getElementById('configurationForm');
    if (form) {
        form.addEventListener('submit', handleFormSubmit);
    }
    
    const applicationSelect = document.getElementById('application');
    if (applicationSelect) {
        applicationSelect.addEventListener('change', updateFanManufacturerState);
        // Initialize state on page load
        updateFanManufacturerState();
    }

    const workbookSelect = document.getElementById('workbookCompressorRow');
    if (workbookSelect) {
        workbookSelect.addEventListener('change', loadWorkbookRowIntoForm);
    }

    const workbookManufacturer = document.getElementById('workbookManufacturer');
    if (workbookManufacturer) {
        workbookManufacturer.addEventListener('change', refreshCapacitiesForManufacturer);
    }
    
    // Initialize workbook-driven generator page controls
    if (document.getElementById('workbookCapacity') && document.getElementById('workbookManufacturer')) {
        await initGeneratorFromWorkbook();
    }
    
    // Display compressors if on config page
    const compressorsList = document.getElementById('compressorsList');
    if (compressorsList) {
        await syncCompressorsFromWorkbook();
        populateTemplateSelect();
        displayCompressors();
    }
});

// Handle form submission - build the selection schema and generate drawings
// directly via the server's /api/generate endpoint.
async function handleFormSubmit(event) {
    event.preventDefault();
    
    // Collect form data
    const circuitCountEl = document.getElementById('circuitCount');
    const voltageEl = document.getElementById('voltage');
    const applicationEl = document.getElementById('application');
    const fanManufacturerEl = document.getElementById('fanmanufacturer');
    const vaporInjectEl = document.getElementById('vaporinject');

    const circuitCount = parseInt((circuitCountEl && circuitCountEl.value) || '0', 10) || 0;
    const voltage = (voltageEl && voltageEl.value) || '';
    const application = (applicationEl && applicationEl.value) || '';
    const fanManufacturer = (fanManufacturerEl && fanManufacturerEl.value) || '';
    const vaporInject = (vaporInjectEl && vaporInjectEl.value) || '';
    
    // Build circuits from workbook-driven selection when available.
    const circuits = [];
    if (workbookGeneratedCircuits.length > 0) {
        workbookGeneratedCircuits.forEach((circuit, circuitIndex) => {
            const compressors = (circuit.compressors || []).map(comp => {
                const libraryMatch = compressorsCache.find(item => {
                    const model = String(item.model || '').toLowerCase();
                    const name = String(item.name || '').toLowerCase();
                    const targetModel = String(comp.model_number || '').toLowerCase();
                    const targetSkid = String(comp.skid_model_number || '').toLowerCase();
                    return model === targetModel || name === targetSkid || model === targetSkid;
                });

                const qty = parseInt(comp.quantity, 10) || 1;
                const sourceTemplates = (Array.isArray(comp.templates) && comp.templates.length > 0)
                    ? comp.templates
                    : ((libraryMatch && libraryMatch.templates) || []);
                const templates = sourceTemplates.map(t => ({
                    name: t.name,
                    quantity: t.scope === 'shared' ? 1 : qty
                }));

                return {
                    model_number: comp.model_number,
                    description: comp.description || comp.skid_model_number || comp.model_number,
                    templates: templates
                };
            });

            circuits.push({
                name: circuit.name || `CU${String(circuitIndex + 1).padStart(3, '0')}`,
                description: circuit.description || '',
                compressors: compressors
            });
        });
    } else {
        // Fallback to existing manual mode if workbook circuits were not loaded.
        for (let i = 1; i <= circuitCount; i++) {
            const compressorNameEl = document.getElementById(`compressorchoice${i}`);
            const quantityEl = document.getElementById(`quantity${i}`);
            const manufacturerEl = document.getElementById(`manu${i}`);

            if (!compressorNameEl || !quantityEl || !manufacturerEl) {
                continue;
            }

            const compressorName = compressorNameEl.value;
            const quantity = parseInt(quantityEl.value) || 1;
            const manufacturer = manufacturerEl.value;

            if (!compressorName) continue;

            const compressor = compressorsCache.find(c => c.name === compressorName);
            const compressorTemplates = (compressor && compressor.templates) || [];

            const templates = compressorTemplates.map(t => ({
                name: t.name,
                quantity: t.scope === 'shared' ? 1 : quantity
            }));

            circuits.push({
                name: `CU${String(i).padStart(3, '0')}`,
                description: `${compressorName} (${manufacturer})`,
                compressors: [
                    {
                        model_number: (compressor && compressor.model) || compressorName,
                        description: (compressor && compressor.name) || compressorName,
                        templates: templates
                    }
                ]
            });
        }
    }
    
    // Validate that at least one circuit is defined
    if (circuits.length === 0) {
        alert('Please select at least one compressor for a circuit.');
        return;
    }
    
    // Create the selection data expected by the CLI's selection adapter
    const selectionData = {
        project_name: "XNNOV Circuit Selection",
        project_number: "PRJ-001",
        revision: "A",
        drawn_by: "User",
        voltage: voltage,
        application: application,
        fan_manufacturer: fanManufacturer,
        vapor_injection: vaporInject,
        circuits: circuits
    };
    
    await generateAndDownload(selectionData);
}

// POST selection data to /api/generate and let the backend run the CLI.
async function generateAndDownload(selectionData) {
    const generateBtn = document.getElementById('generateBtn');
    const originalLabel = generateBtn ? generateBtn.textContent : '';
    if (generateBtn) {
        generateBtn.disabled = true;
        generateBtn.textContent = 'Generating...';
    }
    
    try {
        console.log('[Generate Preview] Payload that will be sent to CLI:', selectionData);

        const response = await fetch('/api/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(selectionData)
        });
        
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            alert('Generation failed: ' + (err.error || response.statusText));
            return;
        }
        
        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/zip')) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'generated_drawings.zip';
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
            alert('Generation completed successfully. The ZIP download has started.');
            return;
        }

        const payload = await response.json().catch(() => ({}));
        console.log('[Generate Preview] Server response:', payload);
        alert(payload.message || 'Generation completed successfully.');
    } catch (error) {
        alert('Error generating drawings: ' + error.message);
        console.error('Generate error:', error);
    } finally {
        if (generateBtn) {
            generateBtn.disabled = false;
            generateBtn.textContent = originalLabel;
        }
    }
}

// Handle saving compressor configuration
async function handleSaveCompressor() {
    const name = document.getElementById('compressorName').value;
    const model = document.getElementById('compressorModel').value;
    const manufacturer = document.getElementById('compressorManufacturer').value;
    const capacity = document.getElementById('compressorCapacity').value;
    
    // Validate input
    if (!name || !model || !manufacturer || !capacity) {
        alert('Please fill in all fields.');
        return;
    }
    
    try {
        const response = await fetch('/api/compressors', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: name,
                model: model,
                manufacturer: manufacturer,
                capacity: parseFloat(capacity),
                templates: []
            })
        });
        
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            alert('Error saving compressor: ' + (err.error || response.statusText));
            return;
        }
        
        // Clear form
        document.getElementById('compressorName').value = '';
        document.getElementById('compressorModel').value = '';
        document.getElementById('compressorManufacturer').value = '';
        document.getElementById('compressorCapacity').value = '';
        
        // Refresh displays
        await fetchCompressors();
        displayCompressors();
        
        alert('Compressor saved successfully!');
    } catch (error) {
        alert('Error saving compressor: ' + error.message);
        console.error('Save compressor error:', error);
    }
}

// Handle compressor selection from the middle column
function selectCompressor(compressorId) {
    const compressor = compressorsCache.find(c => c.id == compressorId);
    
    if (!compressor) return;
    
    // Store selected compressor ID for template operations
    window.selectedCompressorId = compressorId;
    
    // Show details and template sections
    document.getElementById('selectedCompressorDetails').style.display = 'block';
    document.getElementById('templateManagementSection').style.display = 'block';
    document.getElementById('emptyState').style.display = 'none';
    
    // Display compressor details
    const detailsContent = document.getElementById('detailsContent');
    detailsContent.innerHTML = `
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px;">
            <div style="padding: 10px; border: 1px solid #ececec; border-radius: 4px;">
                <strong style="color: #667eea; font-size: 12px;">Name</strong>
                <div style="margin-top: 4px; color: #333;">${compressor.name}</div>
            </div>
            <div style="padding: 10px; border: 1px solid #ececec; border-radius: 4px;">
                <strong style="color: #667eea; font-size: 12px;">Model</strong>
                <div style="margin-top: 4px; color: #333;">${compressor.model}</div>
            </div>
            <div style="padding: 10px; border: 1px solid #ececec; border-radius: 4px;">
                <strong style="color: #667eea; font-size: 12px;">Manufacturer</strong>
                <div style="margin-top: 4px; color: #333;">${compressor.manufacturer}</div>
            </div>
            <div style="padding: 10px; border: 1px solid #ececec; border-radius: 4px;">
                <strong style="color: #667eea; font-size: 12px;">Capacity</strong>
                <div style="margin-top: 4px; color: #333;">${compressor.capacity} kW</div>
            </div>
            <div style="padding: 10px; border: 1px solid #ececec; border-radius: 4px;">
                <strong style="color: #667eea; font-size: 12px;">Templates</strong>
                <div style="margin-top: 4px; color: #333;">${(compressor.templates || []).length}</div>
            </div>
        </div>
    `;
    
    // Reset template selector
    const templateNameSelect = document.getElementById('templateName');
    if (templateNameSelect) templateNameSelect.value = '';
    
    // Display templates
    displaySelectedTemplates(compressorId);
    
    // Highlight selected compressor in list
    document.querySelectorAll('[data-compressor-row]').forEach(row => {
        row.style.background = '#ffffff';
    });
    const selectedRow = document.querySelector(`[data-compressor-id="${compressorId}"]`);
    if (selectedRow) {
        selectedRow.style.background = '#f0f7ff';
    }
}

// Persist a compressor's full template list to the server
async function updateCompressorTemplates(compressorId, templates) {
    return fetch(`/api/compressors/${compressorId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ templates: templates })
    });
}

// Handle adding template to compressor
async function handleAddTemplate() {
    const compressorId = window.selectedCompressorId;
    const templateName = document.getElementById('templateName').value;
    
    if (!compressorId || !templateName) {
        alert('Please choose a template.');
        return;
    }
    
    await fetchCompressors();
    const compressor = compressorsCache.find(c => c.id == compressorId);
    
    if (!compressor) {
        alert('Compressor not found.');
        return;
    }
    
    const templates = compressor.templates || [];
    
    // Check if template already exists
    const templateExists = templates.some(t => t.name === templateName);
    
    if (templateExists) {
        alert('This template is already added to this compressor.');
        return;
    }
    
    const updatedTemplates = [
        ...templates,
        {
            id: createTemplateId(),
            name: templateName,
            scope: 'per_unit',
            type: inferTemplateType(templateName)
        }
    ];
    
    try {
        const response = await updateCompressorTemplates(compressorId, updatedTemplates);
        
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            alert('Error adding template: ' + (err.error || response.statusText));
            return;
        }
        
        // Reset selector
        const templateNameSelect = document.getElementById('templateName');
        if (templateNameSelect) templateNameSelect.value = '';
        
        // Refresh display
        await fetchCompressors();
        displaySelectedTemplates(compressorId);
        displayCompressors();
        
        alert('Template added successfully!');
    } catch (error) {
        alert('Error adding template: ' + error.message);
        console.error('Add template error:', error);
    }
}

// Display templates for selected compressor
function displaySelectedTemplates(compressorId) {
    const compressor = compressorsCache.find(c => c.id == compressorId);
    const selectedTemplatesList = document.getElementById('selectedTemplatesList');
    const bulkActions = document.getElementById('templateBulkActions');
    const selectAll = document.getElementById('selectAllTemplates');
    const removeSelectedBtn = document.getElementById('removeSelectedTemplatesBtn');
    
    if (!compressor || !selectedTemplatesList) return;
    
    const templates = compressor.templates || [];

    if (bulkActions) bulkActions.style.display = templates.length > 0 ? 'block' : 'none';
    if (selectAll) selectAll.checked = false;
    if (removeSelectedBtn) removeSelectedBtn.disabled = true;
    
    const rowsHtml = templates.length > 0
        ? templates
            .map(template => {
                const templateId = String(template.id ?? createTemplateId());
                const encodedTemplateId = encodeURIComponent(templateId);
                return `
                    <tr>
                        <td style="padding: 10px; border-bottom: 1px solid #eee;">
                            <label style="display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: #555;">
                                <input type="checkbox" class="template-select" data-template-id="${encodedTemplateId}" onchange="onTemplateSelectionChanged()">
                                Select
                            </label>
                        </td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee; font-weight: 600; color: #333;">${template.name || ''}</td>
                        <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: right;">
                            <button onclick="handleRemoveTemplate(${compressorId}, '${encodedTemplateId}')" style="padding: 6px 12px; background: #e74c3c; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 13px;">
                                Remove
                            </button>
                        </td>
                    </tr>
                `;
            })
            .join('')
        : `
            <tr>
                <td colspan="3" style="padding: 14px; color: #999; text-align: center;">No templates added yet</td>
            </tr>
        `;

    selectedTemplatesList.innerHTML = `
        <table style="width: 100%; border-collapse: collapse; font-size: 13px; background: #ffffff; border: 1px solid #e0e0e0; border-radius: 6px; overflow: hidden;">
            <thead>
                <tr style="background: #f2f4f8; text-align: left;">
                    <th style="padding: 10px; border-bottom: 1px solid #ddd; width: 120px;">Select</th>
                    <th style="padding: 10px; border-bottom: 1px solid #ddd;">Template</th>
                    <th style="padding: 10px; border-bottom: 1px solid #ddd; text-align: right; width: 120px;">Action</th>
                </tr>
            </thead>
            <tbody>${rowsHtml}</tbody>
        </table>
    `;
}

function getSelectedTemplateIds() {
    return Array.from(document.querySelectorAll('.template-select:checked'))
    .map(item => decodeURIComponent(item.getAttribute('data-template-id') || ''))
    .filter(item => item !== '');
}

function onTemplateSelectionChanged() {
    const allCheckboxes = Array.from(document.querySelectorAll('.template-select'));
    const selectedCount = getSelectedTemplateIds().length;
    const selectAll = document.getElementById('selectAllTemplates');
    const removeSelectedBtn = document.getElementById('removeSelectedTemplatesBtn');

    if (removeSelectedBtn) {
        removeSelectedBtn.disabled = selectedCount === 0;
        removeSelectedBtn.textContent = selectedCount > 0 ? `Remove Selected (${selectedCount})` : 'Remove Selected';
    }

    if (selectAll) {
        selectAll.checked = allCheckboxes.length > 0 && selectedCount === allCheckboxes.length;
    }
}

function toggleSelectAllTemplates() {
    const selectAll = document.getElementById('selectAllTemplates');
    const shouldSelect = !!(selectAll && selectAll.checked);

    document.querySelectorAll('.template-select').forEach(item => {
        item.checked = shouldSelect;
    });

    onTemplateSelectionChanged();
}

async function handleRemoveSelectedTemplates() {
    const compressorId = window.selectedCompressorId;
    const selectedIds = getSelectedTemplateIds();

    if (!compressorId) {
        alert('Please select a compressor first.');
        return;
    }

    if (selectedIds.length === 0) {
        alert('Select at least one template to remove.');
        return;
    }

    if (!confirm(`Remove ${selectedIds.length} selected template(s)?`)) {
        return;
    }

    await fetchCompressors();
    const compressor = compressorsCache.find(c => c.id == compressorId);
    if (!compressor || !compressor.templates) return;

    const selectedSet = new Set(selectedIds);
    const updatedTemplates = compressor.templates.filter(t => !selectedSet.has(String(t.id ?? '')));

    try {
        const response = await updateCompressorTemplates(compressorId, updatedTemplates);

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            alert('Error removing templates: ' + (err.error || response.statusText));
            return;
        }

        await fetchCompressors();
        displaySelectedTemplates(compressorId);
        displayCompressors();
    } catch (error) {
        alert('Error removing templates: ' + error.message);
        console.error('Remove selected templates error:', error);
    }
}

// Remove template from compressor
async function handleRemoveTemplate(compressorId, templateId) {
    if (!confirm('Are you sure you want to remove this template?')) return;
    
    await fetchCompressors();
    const compressor = compressorsCache.find(c => c.id == compressorId);
    if (!compressor || !compressor.templates) return;

    const decodedTemplateId = decodeURIComponent(String(templateId || ''));
    
    const updatedTemplates = compressor.templates.filter(t => String(t.id ?? '') !== decodedTemplateId);
    
    try {
        const response = await updateCompressorTemplates(compressorId, updatedTemplates);
        
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            alert('Error removing template: ' + (err.error || response.statusText));
            return;
        }
        
        await fetchCompressors();
        displaySelectedTemplates(compressorId);
        displayCompressors();
    } catch (error) {
        alert('Error removing template: ' + error.message);
        console.error('Remove template error:', error);
    }
}

// Display saved compressors
function displayCompressors() {
    const compressors = [...compressorsCache].sort((a, b) => {
        const manufacturerA = String(a.manufacturer || '').toLowerCase();
        const manufacturerB = String(b.manufacturer || '').toLowerCase();
        const manufacturerCompare = manufacturerA.localeCompare(manufacturerB);
        if (manufacturerCompare !== 0) {
            return manufacturerCompare;
        }

        const capacityA = Number(a.capacity) || 0;
        const capacityB = Number(b.capacity) || 0;
        if (capacityA !== capacityB) {
            return capacityA - capacityB;
        }

        return String(a.name || '').localeCompare(String(b.name || ''));
    });
    const table = document.getElementById('compressorsTable');
    
    if (!table) return;
    
    if (compressors.length === 0) {
        table.innerHTML = '<p style="color: #999; text-align: center; padding: 20px;">No compressors found</p>';
        return;
    }

    const rowsHtml = compressors
        .map(comp => {
            const templateCount = (comp.templates || []).length;
            return `
                <tr data-compressor-row data-compressor-id="${comp.id}" onclick="selectCompressor(${comp.id})" style="cursor: pointer; background: #ffffff;">
                    <td style="padding: 10px; border-bottom: 1px solid #eee; font-weight: 600;">${comp.name || ''}</td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;">${comp.model || ''}</td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;">${comp.manufacturer || ''}</td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;">${comp.capacity || ''}</td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: center;">${templateCount}</td>
                </tr>
            `;
        })
        .join('');

    table.innerHTML = `
        <table style="width: 100%; border-collapse: collapse; font-size: 13px; background: #ffffff; border: 1px solid #e0e0e0; border-radius: 6px; overflow: hidden;">
            <thead>
                <tr style="background: #f2f4f8; text-align: left;">
                    <th style="padding: 10px; border-bottom: 1px solid #ddd;">Name</th>
                    <th style="padding: 10px; border-bottom: 1px solid #ddd;">Model</th>
                    <th style="padding: 10px; border-bottom: 1px solid #ddd;">Manufacturer</th>
                    <th style="padding: 10px; border-bottom: 1px solid #ddd;">Capacity (T)</th>
                    <th style="padding: 10px; border-bottom: 1px solid #ddd; text-align: center;">Templates</th>
                </tr>
            </thead>
            <tbody>${rowsHtml}</tbody>
        </table>
    `;

    if (window.selectedCompressorId != null) {
        const selectedRow = document.querySelector(`[data-compressor-id="${window.selectedCompressorId}"]`);
        if (selectedRow) {
            selectedRow.style.background = '#f0f7ff';
        }
    }
}

// Delete compressor
async function deleteCompressor(id) {
    if (!confirm('Are you sure you want to delete this compressor?')) return;
    
    try {
        const response = await fetch(`/api/compressors/${id}`, { method: 'DELETE' });
        
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            alert('Error deleting compressor: ' + (err.error || response.statusText));
            return;
        }
        
        // Clear the right column if the deleted compressor was selected
        if (window.selectedCompressorId == id) {
            document.getElementById('selectedCompressorDetails').style.display = 'none';
            document.getElementById('templateManagementSection').style.display = 'none';
            document.getElementById('emptyState').style.display = 'block';
            window.selectedCompressorId = null;
        }
        
        await fetchCompressors();
        displayCompressors();
    } catch (error) {
        alert('Error deleting compressor: ' + error.message);
        console.error('Delete compressor error:', error);
    }
}

// Export compressors to JSON file (server-generated)
function handleExportCompressors() {
    if (compressorsCache.length === 0) {
        alert('No compressors to export. Please create at least one compressor first.');
        return;
    }
    
    window.location.href = '/api/compressors/export';
}

// Import compressors from JSON file
function handleImportCompressors(event) {
    const file = event.target.files[0];
    
    if (!file) {
        return;
    }
    
    const reader = new FileReader();
    
    reader.onload = async function(e) {
        try {
            const data = JSON.parse(e.target.result);
            
            // Validate the imported data
            if (!data.compressors || !Array.isArray(data.compressors)) {
                alert('Invalid file format. Expected a compressors array.');
                return;
            }
            
            // Ask user if they want to merge or replace
            const choice = confirm(
                'Do you want to:\n' +
                'OK: Merge with existing compressors\n' +
                'Cancel: Replace all existing compressors'
            );
            
            const response = await fetch('/api/compressors/import', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    compressors: data.compressors,
                    mode: choice ? 'merge' : 'replace'
                })
            });
            
            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                alert('Error importing compressors: ' + (err.error || response.statusText));
                return;
            }
            
            const result = await response.json();
            
            // Refresh the display
            await fetchCompressors();
            displayCompressors();
            
            alert(`Successfully imported ${result.imported} compressor(s)!`);
        } catch (error) {
            alert('Error reading file: ' + error.message);
            console.error('Import error:', error);
        }
    };
    
    reader.readAsText(file);
    
    // Reset the file input so the same file can be imported again
    event.target.value = '';
}

