// Global configuration loaded from JSON
let compressorConfig = null;

// Load configuration from JSON file
async function loadConfiguration() {
    try {
        const response = await fetch('compressor_config.json');
        compressorConfig = await response.json();
        console.log('Configuration loaded:', compressorConfig);
    } catch (error) {
        console.error('Error loading configuration:', error);
        // Use default config if file fails to load
        compressorConfig = {
            manufacturers: ["Copeland", "Mitsubishi", "Schneider"],
            applications: ["ASHP-CU", "WSHP-CU", "AWHP-2P", "AWHP-4P"],
            templateTypes: {
                regular: [
        "1 EXD-SH2",
        "1 EXD-SH2-1-TRANS",
        "1_Condenser_Fan",
        "2_Condenser_Fan",
        "2_Supply_Fan",
        "3_Return_Fan",
        "3_Supply_Fan",
        "AHU_HEAT_COILee",
        "C063",
        "CD-FAN fans-tech",
        "CD-FAN1-C fans-tech",
        "ENTH-WHEEL",
        "GAS SENSOR",
        "Humidifier",
        "IB-G",
        "SUPPLY DAMPERS",
        "VFD-CD",
        "VFD-L",
        "VFD-l MS"],
                controller: ["Controller-A", "Controller-B", "Controller-C"],
                io: ["IO-Input-1", "IO-Input-2", "IO-Output-1", "IO-Output-2"],
                ladder: ["Ladder-Basic", "Ladder-Advanced", "Ladder-Custom"],
                ladder_component: ["Component-Relay", "Component-Timer", "Component-Counter"],
                valves: ["Valve-Solenoid", "Valve-Check", "Valve-Relief"]
            }
        };
    }
}

const compressorOptions = [
    "Compressor A",
    "Compressor B",
    "Compressor C",
    "Compressor D"
];

function getCompressorOptions() {
    // Try to get from localStorage first
    const savedCompressors = JSON.parse(localStorage.getItem('compressors')) || [];
    
    if (savedCompressors.length > 0) {
        return savedCompressors.map(c => c.name);
    }
    
    // Fall back to default options
    return compressorOptions;
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
document.addEventListener('DOMContentLoaded', function() {
    // Load configuration from JSON
    loadConfiguration();
    
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
    
    // Display compressors if on config page
    const compressorsList = document.getElementById('compressorsList');
    if (compressorsList) {
        displayCompressors();
    }
});

// Handle form submission - generate JSON and download locally
function handleFormSubmit(event) {
    event.preventDefault();
    
    // Collect form data
    const circuitCount = parseInt(document.getElementById('circuitCount').value);
    const voltage = document.getElementById('voltage').value;
    const application = document.getElementById('application').value;
    const fanManufacturer = document.getElementById('fanmanufacturer').value;
    const vaporInject = document.getElementById('vaporinject').value;
    
    // Collect circuit data
    const circuits = [];
    for (let i = 1; i <= circuitCount; i++) {
        const compressor = document.getElementById(`compressorchoice${i}`).value;
        const quantity = parseInt(document.getElementById(`quantity${i}`).value);
        const manufacturer = document.getElementById(`manu${i}`).value;
        
        if (compressor) {
            circuits.push({
                circuit_id: `CU${String(i).padStart(3, '0')}`,
                compressor_model: compressor,
                compressor_description: compressor,
                quantity: quantity,
                manufacturer: manufacturer
            });
        }
    }
    
    // Validate that at least one circuit is defined
    if (circuits.length === 0) {
        alert('Please select at least one compressor for a circuit.');
        return;
    }
    
    // Create the JSON object for CLI
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
    
    // Generate and download JSON file
    downloadJSON(selectionData);
}

// Download JSON file locally
function downloadJSON(data) {
    const timestamp = new Date().toISOString().slice(0, 10);
    const filename = `selection_${timestamp}.json`;
    
    // Create blob from JSON data
    const jsonString = JSON.stringify(data, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json' });
    
    // Create download link
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    
    // Trigger download
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    // Clean up
    URL.revokeObjectURL(url);
    
    // Show instructions
    alert(`Selection data saved as: ${filename}\n\nTo generate drawings, run:\npython app.py --generate-from-selection ${filename} --output ./output`);
}

// Handle saving compressor configuration
function handleSaveCompressor() {
    const name = document.getElementById('compressorName').value;
    const model = document.getElementById('compressorModel').value;
    const manufacturer = document.getElementById('compressorManufacturer').value;
    const capacity = document.getElementById('compressorCapacity').value;
    
    // Validate input
    if (!name || !model || !manufacturer || !capacity) {
        alert('Please fill in all fields.');
        return;
    }
    
    // Get existing compressors from localStorage
    let compressors = JSON.parse(localStorage.getItem('compressors')) || [];
    
    // Add new compressor with empty templates array
    compressors.push({
        id: Date.now(),
        name: name,
        model: model,
        manufacturer: manufacturer,
        capacity: parseFloat(capacity),
        templates: []  // Add templates array
    });
    
    // Save to localStorage
    localStorage.setItem('compressors', JSON.stringify(compressors));
    
    // Clear form
    document.getElementById('compressorName').value = '';
    document.getElementById('compressorModel').value = '';
    document.getElementById('compressorManufacturer').value = '';
    document.getElementById('compressorCapacity').value = '';
    
    // Refresh displays
    displayCompressors();
    populateCompressorSelect();
    
    alert('Compressor saved successfully!');
}

// Handle compressor selection from the middle column
function selectCompressor(compressorId) {
    const compressors = JSON.parse(localStorage.getItem('compressors')) || [];
    const compressor = compressors.find(c => c.id == compressorId);
    
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
        <div style="margin-bottom: 12px;">
            <strong style="color: #667eea;">Name:</strong><br>${compressor.name}
        </div>
        <div style="margin-bottom: 12px;">
            <strong style="color: #667eea;">Model:</strong><br>${compressor.model}
        </div>
        <div style="margin-bottom: 12px;">
            <strong style="color: #667eea;">Manufacturer:</strong><br>${compressor.manufacturer}
        </div>
        <div style="margin-bottom: 12px;">
            <strong style="color: #667eea;">Capacity:</strong><br>${compressor.capacity} kW
        </div>
        <button type="button" onclick="deleteCompressor(${compressorId})" style="width: 100%; padding: 8px; background: #e74c3c; color: white; border: none; border-radius: 4px; cursor: pointer; margin-top: 10px;">
            Delete Compressor
        </button>
    `;
    
    // Reset template selectors
    document.getElementById('templateType').value = '';
    document.getElementById('templateName').innerHTML = '<option value="">-- Choose template --</option>';
    
    // Display templates
    displaySelectedTemplates(compressorId);
    
    // Highlight selected compressor in list
    document.querySelectorAll('[data-compressor-item]').forEach(item => {
        item.style.borderLeft = '4px solid transparent';
        item.style.background = '#ffffff';
    });
    document.querySelector(`[data-compressor-id="${compressorId}"]`).style.borderLeft = '4px solid #667eea';
    document.querySelector(`[data-compressor-id="${compressorId}"]`).style.background = '#f0f7ff';
}

// Handle template type selection
function onTemplateTypeSelected() {
    const templateType = document.getElementById('templateType').value;
    const templateNameSelect = document.getElementById('templateName');
    
    if (!templateType) {
        templateNameSelect.innerHTML = '<option value="">-- Choose a template --</option>';
        return;
    }
    
    // Get templates from loaded configuration
    const templates = (compressorConfig && compressorConfig.templateTypes && compressorConfig.templateTypes[templateType]) || [];
    
    // Clear and populate template name select
    templateNameSelect.innerHTML = '<option value="">-- Choose a template --</option>';
    
    templates.forEach(template => {
        const option = document.createElement('option');
        option.value = template;
        option.textContent = template;
        templateNameSelect.appendChild(option);
    });
}

// Handle adding template to compressor
function handleAddTemplate() {
    const compressorId = window.selectedCompressorId;
    const templateType = document.getElementById('templateType').value;
    const templateName = document.getElementById('templateName').value;
    
    if (!compressorId || !templateType || !templateName) {
        alert('Please select a template type and template.');
        return;
    }
    
    // Get compressors
    let compressors = JSON.parse(localStorage.getItem('compressors')) || [];
    const compressor = compressors.find(c => c.id == compressorId);
    
    if (!compressor) {
        alert('Compressor not found.');
        return;
    }
    
    // Initialize templates array if it doesn't exist
    if (!compressor.templates) {
        compressor.templates = [];
    }
    
    // Check if template already exists
    const templateExists = compressor.templates.some(t => 
        t.type === templateType && t.name === templateName
    );
    
    if (templateExists) {
        alert('This template is already added to this compressor.');
        return;
    }
    
    // Add template
    compressor.templates.push({
        id: Date.now(),
        type: templateType,
        name: templateName
    });
    
    // Save back to localStorage
    localStorage.setItem('compressors', JSON.stringify(compressors));
    
    // Reset selectors
    document.getElementById('templateType').value = '';
    document.getElementById('templateName').innerHTML = '<option value="">-- Choose template --</option>';
    
    // Refresh display
    displaySelectedTemplates(compressorId);
    displayCompressors();
    
    alert('Template added successfully!');
}

// Display templates for selected compressor
function displaySelectedTemplates(compressorId) {
    const compressors = JSON.parse(localStorage.getItem('compressors')) || [];
    const compressor = compressors.find(c => c.id == compressorId);
    const selectedTemplatesList = document.getElementById('selectedTemplatesList');
    
    if (!compressor || !selectedTemplatesList) return;
    
    const templates = compressor.templates || [];
    
    if (templates.length === 0) {
        selectedTemplatesList.innerHTML = '<p style="color: #999; text-align: center; padding: 20px;">No templates added yet</p>';
        return;
    }
    
    let html = '';
    templates.forEach(template => {
        html += `
            <div style="
                padding: 12px;
                margin-bottom: 10px;
                background: white;
                border-radius: 4px;
                border-left: 4px solid #667eea;
                display: flex;
                justify-content: space-between;
                align-items: center;
                border: 1px solid #e0e0e0;
            ">
                <div>
                    <div style="font-weight: 600; color: #333; margin-bottom: 4px;">${template.name}</div>
                    <div style="font-size: 12px; color: #666;">${capitalizeTemplateType(template.type)}</div>
                </div>
                <button onclick="handleRemoveTemplate(${compressorId}, ${template.id})" style="padding: 6px 12px; background: #e74c3c; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 13px;">
                    Remove
                </button>
            </div>
        `;
    });
    
    selectedTemplatesList.innerHTML = html;
}

// Remove template from compressor
function handleRemoveTemplate(compressorId, templateId) {
    if (confirm('Are you sure you want to remove this template?')) {
        let compressors = JSON.parse(localStorage.getItem('compressors')) || [];
        const compressor = compressors.find(c => c.id == compressorId);
        
        if (compressor && compressor.templates) {
            compressor.templates = compressor.templates.filter(t => t.id !== templateId);
            localStorage.setItem('compressors', JSON.stringify(compressors));
            displaySelectedTemplates(compressorId);
            displayCompressors();
        }
    }
}

// Helper function to capitalize template type
function capitalizeTemplateType(type) {
    const names = {
        'regular': 'Regular Template',
        'controller': 'Controller',
        'io': 'IO',
        'ladder': 'Ladder',
        'ladder_component': 'Ladder Component',
        'valves': 'Valve'
    };
    return names[type] || type;
}

// Display saved compressors
function displayCompressors() {
    const compressors = JSON.parse(localStorage.getItem('compressors')) || [];
    const table = document.getElementById('compressorsTable');
    
    if (!table) return;
    
    if (compressors.length === 0) {
        table.innerHTML = '<p style="color: #999; text-align: center; padding: 20px;">No compressors yet</p>';
        return;
    }
    
    let html = '';
    compressors.forEach(comp => {
        const templateCount = (comp.templates || []).length;
        html += `
            <div 
                data-compressor-item 
                data-compressor-id="${comp.id}" 
                onclick="selectCompressor(${comp.id})" 
                style="
                    padding: 12px;
                    margin-bottom: 10px;
                    background: #ffffff;
                    border-radius: 4px;
                    border-left: 4px solid transparent;
                    cursor: pointer;
                    transition: all 0.2s ease;
                    border: 1px solid #e0e0e0;
                "
                onmouseover="this.style.background='#f5f5f5'"
                onmouseout="this.style.background='#ffffff'"
            >
                <div style="font-weight: 600; color: #333; margin-bottom: 4px;">${comp.name}</div>
                <div style="font-size: 12px; color: #666; margin-bottom: 4px;">
                    <strong>Model:</strong> ${comp.model}
                </div>
                <div style="font-size: 12px; color: #666; margin-bottom: 4px;">
                    <strong>Capacity:</strong> ${comp.capacity} kW
                </div>
                <div style="font-size: 12px; color: #667eea;">
                    <strong>Templates:</strong> <span style="background: #667eea; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">${templateCount}</span>
                </div>
            </div>
        `;
    });
    
    table.innerHTML = html;
}

// Delete compressor
function deleteCompressor(id) {
    if (confirm('Are you sure you want to delete this compressor?')) {
        let compressors = JSON.parse(localStorage.getItem('compressors')) || [];
        compressors = compressors.filter(c => c.id !== id);
        localStorage.setItem('compressors', JSON.stringify(compressors));
        
        // Clear the right column if the deleted compressor was selected
        if (window.selectedCompressorId == id) {
            document.getElementById('selectedCompressorDetails').style.display = 'none';
            document.getElementById('templateManagementSection').style.display = 'none';
            document.getElementById('emptyState').style.display = 'block';
            window.selectedCompressorId = null;
        }
        
        displayCompressors();
    }
}

// Export compressors to JSON file
function handleExportCompressors() {
    const compressors = JSON.parse(localStorage.getItem('compressors')) || [];
    
    if (compressors.length === 0) {
        alert('No compressors to export. Please create at least one compressor first.');
        return;
    }
    
    const exportData = {
        version: '1.0',
        exportDate: new Date().toISOString(),
        compressors: compressors
    };
    
    const filename = `compressors_${new Date().toISOString().split('T')[0]}.json`;
    downloadJSON(exportData, filename);
    
    alert(`Compressor configuration exported successfully as: ${filename}`);
}

// Import compressors from JSON file
function handleImportCompressors(event) {
    const file = event.target.files[0];
    
    if (!file) {
        return;
    }
    
    const reader = new FileReader();
    
    reader.onload = function(e) {
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
            
            let compressors;
            if (choice) {
                // Merge: get existing and add new ones
                const existing = JSON.parse(localStorage.getItem('compressors')) || [];
                compressors = [...existing, ...data.compressors];
            } else {
                // Replace: use only imported data
                compressors = data.compressors;
            }
            
            // Save to localStorage
            localStorage.setItem('compressors', JSON.stringify(compressors));
            
            // Refresh the display
            displayCompressors();
            populateCompressorSelect();
            
            const count = data.compressors.length;
            alert(`Successfully imported ${count} compressor(s)!`);
        } catch (error) {
            alert('Error reading file: ' + error.message);
            console.error('Import error:', error);
        }
    };
    
    reader.readAsText(file);
    
    // Reset the file input so the same file can be imported again
    event.target.value = '';
}

// Helper function to download JSON (reused from other parts of the app)
function downloadJSON(data, filename) {
    const jsonString = JSON.stringify(data, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json' });
    
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    URL.revokeObjectURL(url);
}

