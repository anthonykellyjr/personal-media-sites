// functions.js
let hasChanges = false;
let originalData = {};
let serviceMetadata = {};
const API_URL = '/api';

// Initialize the page
window.addEventListener('DOMContentLoaded', async function() {
    await loadServiceMetadata();
    await loadSavedData();
    renderServices();
    setupChangeTracking();
});

// Load service metadata
async function loadServiceMetadata() {
    try {
        const response = await fetch(`${API_URL}/services-metadata`);
        if (response.ok) {
            serviceMetadata = await response.json();
        }
    } catch (error) {
        console.error('Error loading service metadata:', error);
        // Fallback to empty metadata
        serviceMetadata = { tower: {}, mac: {} };
    }
}

// Load saved data from backend
async function loadSavedData() {
    try {
        const response = await fetch(`${API_URL}/docker-services`);
        if (response.ok) {
            const data = await response.json();
            originalData = data;
        } else if (response.status === 404) {
            console.log('No saved data found, using defaults');
            originalData = { tower: {}, mac: {} };
        }
    } catch (error) {
        console.error('Error loading data:', error);
        originalData = { tower: {}, mac: {} };
    }
}

// Render all services
function renderServices() {
    ['tower', 'mac'].forEach(host => {
        const activeTableBody = document.getElementById(`${host}-active-tbody`);
        const inactiveSection = document.getElementById(`${host}-inactive-section`);
        const inactiveAccordions = document.getElementById(`${host}-inactive-accordions`);
        
        // Clear existing content
        activeTableBody.innerHTML = '';
        inactiveAccordions.innerHTML = '';
        
        let hasInactive = false;
        
        // Get all services for this host
        const services = { ...serviceMetadata[host] };
        
        // Render each service
        Object.keys(services).forEach(serviceName => {
            const metadata = services[serviceName] || {};
            const savedData = originalData[host]?.[serviceName] || {};
            const isActive = savedData.active !== false; // Default to active if not specified
            
            const serviceData = {
                name: serviceName,
                active: isActive,
                port: metadata.port || '-',
                website: savedData.website || '',
                domain: savedData.domain || '',
                description: savedData.description || '',
                cpu: metadata.cpu || '-',
                ram: metadata.ram || '-',
                network: metadata.network || '-',
                disk: metadata.disk || '-',
                gpu: metadata.gpu || '-'
            };
            
            if (isActive) {
                activeTableBody.appendChild(createServiceRow(serviceData, host));
            } else {
                hasInactive = true;
                inactiveAccordions.appendChild(createServiceAccordion(serviceData, host));
            }
        });
        
        // Show/hide inactive section
        inactiveSection.style.display = hasInactive ? 'block' : 'none';
    });
}

// Create a table row for active services
function createServiceRow(serviceData, host) {
    const row = document.createElement('tr');
    row.setAttribute('data-service', serviceData.name);
    
    row.innerHTML = `
        <td>${serviceData.name}</td>
        <td><input type="checkbox" class="status-checkbox" ${serviceData.active ? 'checked' : ''}></td>
        <td><span class="port">${serviceData.port}</span></td>
        <td><input type="text" class="input-field website-input" value="${serviceData.website}" data-field="website"></td>
        <td><input type="text" class="input-field" placeholder="Enter domain" value="${serviceData.domain}" data-field="domain"></td>
        <td><input type="text" class="input-field" value="${serviceData.description}" data-field="description"></td>
        <td>${getResourceBadge('cpu', serviceData.cpu)}</td>
        <td>${getResourceBadge('ram', serviceData.ram)}</td>
        <td>${getResourceBadge('network', serviceData.network)}</td>
        <td>${getResourceBadge('disk', serviceData.disk)}</td>
        <td>${getResourceBadge('gpu', serviceData.gpu)}</td>
    `;
    
    return row;
}

// Create an accordion for inactive services
function createServiceAccordion(serviceData, host) {
    const accordion = document.createElement('div');
    accordion.className = 'accordion';
    accordion.setAttribute('data-service', serviceData.name);
    
    const header = document.createElement('div');
    header.className = 'accordion-header';
    header.innerHTML = `
        <h3>${serviceData.name}</h3>
        <span class="accordion-chevron">▶</span>
    `;
    
    const content = document.createElement('div');
    content.className = 'accordion-content';
    content.innerHTML = `
        <table class="inactive-services-table">
            <tr>
                <td>Active:</td>
                <td><input type="checkbox" class="status-checkbox" data-service="${serviceData.name}"></td>
            </tr>
            <tr>
                <td>Port:</td>
                <td><span class="port">${serviceData.port}</span></td>
            </tr>
            <tr>
                <td>Website:</td>
                <td><input type="text" class="input-field website-input" value="${serviceData.website}" data-field="website"></td>
            </tr>
            <tr>
                <td>Domain:</td>
                <td><input type="text" class="input-field" placeholder="Enter domain" value="${serviceData.domain}" data-field="domain"></td>
            </tr>
            <tr>
                <td>Description:</td>
                <td><input type="text" class="input-field" value="${serviceData.description}" data-field="description"></td>
            </tr>
            <tr>
                <td>Resources:</td>
                <td>
                    CPU: ${getResourceBadge('cpu', serviceData.cpu)}
                    RAM: ${getResourceBadge('ram', serviceData.ram)}
                    ${serviceData.network !== '-' ? `Network: ${getResourceBadge('network', serviceData.network)}` : ''}
                    ${serviceData.disk !== '-' ? `Disk: ${getResourceBadge('disk', serviceData.disk)}` : ''}
                    ${serviceData.gpu !== '-' ? `GPU: ${getResourceBadge('gpu', serviceData.gpu)}` : ''}
                </td>
            </tr>
        </table>
    `;
    
    header.addEventListener('click', () => {
        accordion.classList.toggle('expanded');
    });
    
    accordion.appendChild(header);
    accordion.appendChild(content);
    
    return accordion;
}

// Get resource badge HTML
function getResourceBadge(type, value) {
    if (value === '-') return '-';
    
    let className = 'resource-badge';
    
    if (type === 'cpu') {
        if (value.includes('High')) className += ' resource-cpu-high';
        else if (value.includes('Medium')) className += ' resource-cpu-med';
        else className += ' resource-cpu-low';
    } else if (type === 'ram') {
        className += ' resource-ram';
    } else if (type === 'network') {
        className += ' resource-net';
    } else if (type === 'disk') {
        className += ' resource-disk';
    } else if (type === 'gpu') {
        className += ' resource-gpu';
    }
    
    return `<span class="${className}">${value}</span>`;
}

// Setup change tracking
function setupChangeTracking() {
    // Use event delegation for dynamically created elements
    document.addEventListener('input', function(event) {
        if (event.target.classList.contains('input-field')) {
            markAsChanged(event);
        }
    });
    
    document.addEventListener('change', function(event) {
        if (event.target.classList.contains('status-checkbox') || event.target.classList.contains('input-field')) {
            handleStatusChange(event);
            markAsChanged(event);
        }
    });
}

// Handle status checkbox changes
function handleStatusChange(event) {
    if (!event.target.classList.contains('status-checkbox')) return;
    
    // If status changed, we need to re-render to move service between active/inactive
    const isChecked = event.target.checked;
    const serviceName = event.target.closest('[data-service]').getAttribute('data-service');
    const host = event.target.closest('.tab-content').id;
    
    // Update the data
    if (!originalData[host]) originalData[host] = {};
    if (!originalData[host][serviceName]) originalData[host][serviceName] = {};
    
    // Collect current values before re-rendering
    const container = event.target.closest('[data-service]');
    const currentData = {
        website: container.querySelector('input[data-field="website"]')?.value || '',
        domain: container.querySelector('input[data-field="domain"]')?.value || '',
        description: container.querySelector('input[data-field="description"]')?.value || '',
        active: isChecked
    };
    
    // Update the data
    Object.assign(originalData[host][serviceName], currentData);
    
    // Re-render services
    setTimeout(() => {
        renderServices();
        setupChangeTracking();
        checkForChanges();
    }, 0);
}

// Mark field as changed
function markAsChanged(event) {
    const input = event.target;
    
    // Visual feedback
    if (input.classList.contains('input-field')) {
        input.classList.add('changed');
    }
    
    // Check if value actually changed from original
    checkForChanges();
}

// Check if there are any changes
function checkForChanges() {
    hasChanges = false;
    
    ['tower', 'mac'].forEach(host => {
        // Check active services
        const activeRows = document.querySelectorAll(`#${host}-active-tbody tr`);
        activeRows.forEach(row => {
            if (checkRowForChanges(row, host)) hasChanges = true;
        });
        
        // Check inactive services
        const inactiveAccordions = document.querySelectorAll(`#${host}-inactive-accordions .accordion`);
        inactiveAccordions.forEach(accordion => {
            if (checkAccordionForChanges(accordion, host)) hasChanges = true;
        });
    });
    
    // Enable/disable save button
    document.getElementById('saveBtn').disabled = !hasChanges;
}

// Check if a row has changes
function checkRowForChanges(row, host) {
    const serviceName = row.getAttribute('data-service');
    const currentData = {
        website: row.querySelector('input[data-field="website"]').value,
        domain: row.querySelector('input[data-field="domain"]').value,
        description: row.querySelector('input[data-field="description"]').value,
        active: row.querySelector('.status-checkbox').checked
    };
    
    const original = originalData[host]?.[serviceName] || {};
    
    return currentData.website !== (original.website || '') ||
           currentData.domain !== (original.domain || '') ||
           currentData.description !== (original.description || '') ||
           currentData.active !== (original.active !== false);
}

// Check if an accordion has changes
function checkAccordionForChanges(accordion, host) {
    const serviceName = accordion.getAttribute('data-service');
    const currentData = {
        website: accordion.querySelector('input[data-field="website"]').value,
        domain: accordion.querySelector('input[data-field="domain"]').value,
        description: accordion.querySelector('input[data-field="description"]').value,
        active: accordion.querySelector('.status-checkbox').checked
    };
    
    const original = originalData[host]?.[serviceName] || {};
    
    return currentData.website !== (original.website || '') ||
           currentData.domain !== (original.domain || '') ||
           currentData.description !== (original.description || '') ||
           currentData.active !== (original.active !== false);
}

// Collect all form data
function collectFormData() {
    const data = { tower: {}, mac: {} };
    
    ['tower', 'mac'].forEach(host => {
        // Collect from active services
        const activeRows = document.querySelectorAll(`#${host}-active-tbody tr`);
        activeRows.forEach(row => {
            const serviceName = row.getAttribute('data-service');
            data[host][serviceName] = {
                website: row.querySelector('input[data-field="website"]').value,
                domain: row.querySelector('input[data-field="domain"]').value,
                description: row.querySelector('input[data-field="description"]').value,
                active: row.querySelector('.status-checkbox').checked
            };
        });
        
        // Collect from inactive services
        const inactiveAccordions = document.querySelectorAll(`#${host}-inactive-accordions .accordion`);
        inactiveAccordions.forEach(accordion => {
            const serviceName = accordion.getAttribute('data-service');
            data[host][serviceName] = {
                website: accordion.querySelector('input[data-field="website"]').value,
                domain: accordion.querySelector('input[data-field="domain"]').value,
                description: accordion.querySelector('input[data-field="description"]').value,
                active: accordion.querySelector('.status-checkbox').checked
            };
        });
    });
    
    return data;
}

// Save changes to backend
async function saveChanges() {
    const data = collectFormData();
    
    try {
        const response = await fetch(`${API_URL}/docker-services`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
        
        if (response.ok) {
            showStatus('Changes saved successfully!', 'success');
            originalData = data;
            
            // Clear changed indicators
            document.querySelectorAll('.changed').forEach(el => {
                el.classList.remove('changed');
            });
            
            document.getElementById('saveBtn').disabled = true;
            hasChanges = false;
        } else {
            showStatus('Failed to save changes', 'error');
        }
    } catch (error) {
        showStatus('Error saving changes: ' + error.message, 'error');
    }
}

// Show status message
function showStatus(message, type) {
    const statusEl = document.getElementById('statusMessage');
    statusEl.textContent = message;
    statusEl.className = `status-message status-${type}`;
    statusEl.style.display = 'block';
    
    setTimeout(() => {
        statusEl.style.display = 'none';
    }, 3000);
}

// Tab switching
function showTab(tabName) {
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.remove('active');
    });
    
    document.getElementById(tabName).classList.add('active');
    event.target.classList.add('active');
    
    const hostName = tabName === 'tower' ? 'Ubuntu Tower' : 'Ubuntu Mac';
    document.getElementById('current-host').textContent = hostName + ' Services';
}

// Export to Excel
function exportToExcel() {
    const wb = XLSX.utils.book_new();
    
    ['tower', 'mac'].forEach(host => {
        const data = [];
        
        // Get current form data
        const formData = collectFormData();
        
        // Export all services with their metadata
        Object.keys(serviceMetadata[host] || {}).forEach(serviceName => {
            const metadata = serviceMetadata[host][serviceName];
            const savedData = formData[host][serviceName] || {};
            
            data.push({
                'Service Name': serviceName,
                'Active': savedData.active ? 'Active' : 'Inactive',
                'Port': metadata.port || '-',
                'Website': savedData.website || '-',
                'Domain': savedData.domain || '',
                'Description': savedData.description || '',
                'CPU': metadata.cpu || '-',
                'RAM': metadata.ram || '-',
                'Network': metadata.network || '-',
                'Disk I/O': metadata.disk || '-',
                'GPU': metadata.gpu || '-'
            });
        });
        
        const ws = XLSX.utils.json_to_sheet(data);
        XLSX.utils.book_append_sheet(wb, ws, host === 'tower' ? 'Ubuntu Tower' : 'Ubuntu Mac');
    });
    
    XLSX.writeFile(wb, "docker_services_catalog.xlsx");
}