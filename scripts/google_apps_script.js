/**
 * Praeto Tender Tracker - Google Apps Script
 * Version: 1.0
 * 
 * This script runs inside Google Sheets to:
 * 1. Auto-format new entries
 * 2. Calculate days remaining
 * 3. Send email alerts for urgent tenders
 * 4. Create dashboard charts
 */

// ============== CONFIGURATION ==============

const CONFIG = {
    SHEET_NAME: 'Tender Tracker',
    RAW_DATA_SHEET: 'Raw_Data',
    DASHBOARD_SHEET: 'Dashboard',
    SETTINGS_SHEET: 'Settings',

    ALERT_DAYS: [30, 14, 7, 3, 1], // Days before closing to send reminder

    TEAM_EMAILS: [
        'jaden@praeto.co.za',
        'admin1@praeto.co.za',
        'admin3@praeto.co.za',
        'jared@praeto.co.za',
        'josh@praeto.co.za'
    ],

    CATEGORIES: {
        'insurance': { color: '#e3f2fd', priority: 1 },
        'advisory_consulting': { color: '#f3e5f5', priority: 2 },
        'civil_engineering': { color: '#e8f5e9', priority: 3 },
        'cleaning_facility': { color: '#fff3e0', priority: 4 },
        'construction': { color: '#fce4ec', priority: 5 }
    }
};

// ============== TRIGGERS ==============

/**
 * Create time-driven trigger to run daily
 */
function createDailyTrigger() {
    // Delete existing triggers
    const triggers = ScriptApp.getProjectTriggers();
    triggers.forEach(trigger => ScriptApp.deleteTrigger(trigger));

    // Create new daily trigger at 8 AM
    ScriptApp.newTrigger('dailyUpdate')
        .timeBased()
        .everyDays(1)
        .atHour(8)
        .nearMinute(0)
        .create();

    Logger.log('Daily trigger created for 8:00 AM');
}

/**
 * Main daily update function
 */
function dailyUpdate() {
    updateDaysRemaining();
    checkUrgentTenders();
    updateDashboard();
    formatSheet();
}

// ============== DATA MANAGEMENT ==============

/**
 * Update days remaining for all active tenders
 */
function updateDaysRemaining() {
    const sheet = SpreadsheetApp.getActiveSpreadsheet();
    const rawData = sheet.getSheetByName(CONFIG.RAW_DATA_SHEET);

    if (!rawData) {
        Logger.log('Raw_Data sheet not found');
        return;
    }

    const data = rawData.getDataRange().getValues();
    const headers = data[0];
    const closingDateCol = headers.indexOf('Closing_Date');
    const daysRemainingCol = headers.indexOf('Days_Remaining');
    const statusCol = headers.indexOf('Status');

    if (closingDateCol === -1 || daysRemainingCol === -1) {
        Logger.log('Required columns not found');
        return;
    }

    const today = new Date();
    let updatedCount = 0;

    // Start from row 2 (skip header)
    for (let i = 1; i < data.length; i++) {
        const closingDate = data[i][closingDateCol];
        const currentStatus = data[i][statusCol];

        if (closingDate && currentStatus !== 'Closed' && currentStatus !== 'Awarded') {
            const daysLeft = Math.ceil((closingDate - today) / (1000 * 60 * 60 * 24));

            // Update days remaining
            rawData.getRange(i + 1, daysRemainingCol + 1).setValue(Math.max(0, daysLeft));

            // Auto-update status if expired
            if (daysLeft < 0) {
                rawData.getRange(i + 1, statusCol + 1).setValue('Closed');
            }

            updatedCount++;
        }
    }

    Logger.log(`Updated ${updatedCount} tenders`);
}

/**
 * Check for urgent tenders and send alerts
 */
function checkUrgentTenders() {
    const sheet = SpreadsheetApp.getActiveSpreadsheet();
    const rawData = sheet.getSheetByName(CONFIG.RAW_DATA_SHEET);

    const data = rawData.getDataRange().getValues();
    const headers = data[0];

    const daysRemainingCol = headers.indexOf('Days_Remaining');
    const alertSentCol = headers.indexOf('Alert_Sent');
    const buyerCol = headers.indexOf('Buyer');
    const titleCol = headers.indexOf('Title');
    const closingDateCol = headers.indexOf('Closing_Date');
    const categoryCol = headers.indexOf('Category');

    const urgentTenders = [];

    for (let i = 1; i < data.length; i++) {
        const daysLeft = data[i][daysRemainingCol];
        const alertSent = data[i][alertSentCol];

        // Check if urgent and alert not yet sent
        if (daysLeft && CONFIG.ALERT_DAYS.includes(daysLeft) && alertSent !== 'Yes') {
            urgentTenders.push({
                row: i + 1,
                buyer: data[i][buyerCol],
                title: data[i][titleCol],
                daysLeft: daysLeft,
                closingDate: data[i][closingDateCol],
                category: data[i][categoryCol]
            });
        }
    }

    // Send consolidated alert
    if (urgentTenders.length > 0) {
        sendUrgentAlert(urgentTenders);

        // Mark alerts as sent
        urgentTenders.forEach(tender => {
            rawData.getRange(tender.row, alertSentCol + 1).setValue('Yes');
        });
    }
}

/**
 * Send email alert for urgent tenders
 */
function sendUrgentAlert(tenders) {
    const subject = `🚨 URGENT: ${tenders.length} Tender(s) Closing Soon - Praeto`;

    let body = `
    <html>
    <head>
      <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; }
        .header { background: #d32f2f; color: white; padding: 20px; }
        .tender { background: #ffebee; padding: 15px; margin: 10px 0; border-left: 4px solid #d32f2f; }
        .days { font-size: 24px; font-weight: bold; color: #d32f2f; }
      </style>
    </head>
    <body>
      <div class="header">
        <h2>⏰ URGENT TENDER REMINDERS</h2>
        <p>The following tenders require immediate attention:</p>
      </div>
  `;

    tenders.forEach(t => {
        body += `
      <div class="tender">
        <div class="days">${t.daysLeft} DAYS REMAINING</div>
        <p><strong>${t.buyer}</strong></p>
        <p>${t.title}</p>
        <p>Closing: ${t.closingDate} | Category: ${t.category}</p>
      </div>
    `;
    });

    body += `
      <p><a href="${SpreadsheetApp.getActiveSpreadsheet().getUrl()}">View Full Dashboard</a></p>
    </body>
    </html>
  `;

    // Send to team
    CONFIG.TEAM_EMAILS.forEach(email => {
        MailApp.sendEmail({
            to: email,
            subject: subject,
            htmlBody: body,
            name: 'Praeto Tender Tracker'
        });
    });

    Logger.log(`Urgent alert sent for ${tenders.length} tenders`);
}

// ============== DASHBOARD ==============

/**
 * Update dashboard with summary statistics
 */
function updateDashboard() {
    const sheet = SpreadsheetApp.getActiveSpreadsheet();
    const rawData = sheet.getSheetByName(CONFIG.RAW_DATA_SHEET);
    const dashboard = sheet.getSheetByName(CONFIG.DASHBOARD_SHEET);

    if (!rawData || !dashboard) {
        Logger.log('Required sheets not found');
        return;
    }

    const data = rawData.getDataRange().getValues();
    const headers = data[0];

    const categoryCol = headers.indexOf('Category');
    const valueCol = headers.indexOf('Value_ZAR');
    const daysRemainingCol = headers.indexOf('Days_Remaining');
    const statusCol = headers.indexOf('Status');

    // Calculate statistics
    const stats = {
        total: 0,
        byCategory: {},
        byUrgency: {
            'Closing < 7 days': 0,
            'Closing 7-30 days': 0,
            'Closing > 30 days': 0,
            'Expired': 0
        },
        totalValue: 0
    };

    for (let i = 1; i < data.length; i++) {
        const category = data[i][categoryCol] || 'uncategorized';
        const value = parseFloat(data[i][valueCol]) || 0;
        const daysLeft = data[i][daysRemainingCol];
        const status = data[i][statusCol];

        if (status !== 'Closed' && status !== 'Awarded') {
            stats.total++;
            stats.totalValue += value;

            // By category
            stats.byCategory[category] = (stats.byCategory[category] || 0) + 1;

            // By urgency
            if (daysLeft < 0) stats.byUrgency['Expired']++;
            else if (daysLeft <= 7) stats.byUrgency['Closing < 7 days']++;
            else if (daysLeft <= 30) stats.byUrgency['Closing 7-30 days']++;
            else stats.byUrgency['Closing > 30 days']++;
        }
    }

    // Write to dashboard
    dashboard.clear();

    // Header
    dashboard.getRange(1, 1).setValue('TENDER TRACKER DASHBOARD').setFontSize(16).setFontWeight('bold');
    dashboard.getRange(2, 1).setValue(`Last Updated: ${new Date().toLocaleString()}`);

    // Summary
    dashboard.getRange(4, 1).setValue('SUMMARY').setFontWeight('bold');
    dashboard.getRange(5, 1).setValue('Total Active Tenders:');
    dashboard.getRange(5, 2).setValue(stats.total);
    dashboard.getRange(6, 1).setValue('Total Value (ZAR):');
    dashboard.getRange(6, 2).setValue(stats.totalValue).setNumberFormat('R#,##0');

    // By Category
    dashboard.getRange(8, 1).setValue('BY CATEGORY').setFontWeight('bold');
    let row = 9;
    Object.entries(stats.byCategory).forEach(([cat, count]) => {
        dashboard.getRange(row, 1).setValue(cat.replace('_', ' ').toUpperCase());
        dashboard.getRange(row, 2).setValue(count);
        row++;
    });

    // By Urgency
    dashboard.getRange(row + 1, 1).setValue('BY URGENCY').setFontWeight('bold');
    row += 2;
    Object.entries(stats.byUrgency).forEach(([urgency, count]) => {
        dashboard.getRange(row, 1).setValue(urgency);
        dashboard.getRange(row, 2).setValue(count);

        // Color coding
        if (urgency === 'Closing < 7 days' && count > 0) {
            dashboard.getRange(row, 1, 1, 2).setBackground('#ffebee');
        } else if (urgency === 'Closing 7-30 days' && count > 0) {
            dashboard.getRange(row, 1, 1, 2).setBackground('#fff3e0');
        }

        row++;
    });

    // Auto-resize
    dashboard.autoResizeColumns(1, 2);

    Logger.log('Dashboard updated');
}

// ============== FORMATTING ==============

/**
 * Apply conditional formatting and styling
 */
function formatSheet() {
    const sheet = SpreadsheetApp.getActiveSpreadsheet();
    const rawData = sheet.getSheetByName(CONFIG.RAW_DATA_SHEET);

    if (!rawData) return;

    const lastRow = rawData.getLastRow();
    const lastCol = rawData.getLastColumn();

    if (lastRow < 2) return; // No data yet

    // Format header row
    rawData.getRange(1, 1, 1, lastCol)
        .setFontWeight('bold')
        .setBackground('#003366')
        .setFontColor('white');

    // Freeze header row
    rawData.setFrozenRows(1);

    // Conditional formatting for urgency
    const daysRange = rawData.getRange(2, 8, lastRow - 1, 1); // Days_Remaining column

    // Red for < 7 days
    const rule1 = SpreadsheetApp.newConditionalFormatRule()
        .whenNumberLessThan(7)
        .setBackground('#ffebee')
        .setRanges([daysRange])
        .build();

    // Yellow for 7-30 days
    const rule2 = SpreadsheetApp.newConditionalFormatRule()
        .whenNumberBetween(7, 30)
        .setBackground('#fff3e0')
        .setRanges([daysRange])
        .build();

    // Green for > 30 days
    const rule3 = SpreadsheetApp.newConditionalFormatRule()
        .whenNumberGreaterThan(30)
        .setBackground('#e8f5e9')
        .setRanges([daysRange])
        .build();

    const rules = rawData.getConditionalFormatRules();
    rules.push(rule1, rule2, rule3);
    rawData.setConditionalFormatRules(rules);

    // Auto-resize columns
    rawData.autoResizeColumns(1, lastCol);

    Logger.log('Formatting applied');
}

// ============== UTILITY FUNCTIONS ==============

/**
 * Add new tender from scraper (called via HTTP POST)
 */
function doPost(e) {
    const data = JSON.parse(e.postData.contents);

    const sheet = SpreadsheetApp.getActiveSpreadsheet();
    const rawData = sheet.getSheetByName(CONFIG.RAW_DATA_SHEET);

    // Append row
    rawData.appendRow([
        data.date_scraped,
        data.source,
        data.tender_id,
        data.title,
        data.buyer,
        data.category,
        data.closing_date,
        data.days_remaining,
        data.value_zar,
        data.description,
        data.document_link,
        data.status,
        data.priority_buyer ? 'Yes' : 'No',
        'No' // Alert_Sent
    ]);

    return ContentService.createTextOutput(JSON.stringify({
        'result': 'success',
        'tender_id': data.tender_id
    })).setMimeType(ContentService.MimeType.JSON);
}

/**
 * Manual trigger for testing
 */
function manualRun() {
    dailyUpdate();
}
