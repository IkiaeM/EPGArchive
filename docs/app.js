class EPGViewer {
    constructor() {
        this.channels = new Map();
        this.programs = [];
        this.filteredChannels = [];
        this.selectedDate = new Date();
        this.pixelsPerMinute = 2;
        this.dayStartHour = 0;
        this.dayEndHour = 24;
        
        this.init();
    }

    async init() {
        this.bindElements();
        this.bindEvents();
        this.setInitialDate();
        await this.loadAvailableDates();
        await this.loadEPGData();
    }

    bindElements() {
        this.datePicker = document.getElementById('date-picker');
        this.prevDayBtn = document.getElementById('prev-day');
        this.nextDayBtn = document.getElementById('next-day');
        this.channelSearch = document.getElementById('channel-search');
        this.channelList = document.getElementById('channel-list');
        this.channelCount = document.getElementById('channel-count');
        this.timeHeader = document.getElementById('time-header');
        this.epgGrid = document.getElementById('epg-grid');
        this.loading = document.getElementById('loading');
        this.modal = document.getElementById('modal');
        this.modalClose = document.getElementById('modal-close');
    }

    bindEvents() {
        this.datePicker.addEventListener('change', () => this.onDateChange());
        this.prevDayBtn.addEventListener('click', () => this.navigateDay(-1));
        this.nextDayBtn.addEventListener('click', () => this.navigateDay(1));
        this.channelSearch.addEventListener('input', () => this.filterChannels());
        this.modalClose.addEventListener('click', () => this.closeModal());
        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) this.closeModal();
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') this.closeModal();
        });
    }

    setInitialDate() {
        const today = new Date();
        this.selectedDate = today;
        this.datePicker.value = this.formatDateForInput(today);
    }

    formatDateForInput(date) {
        return date.toISOString().split('T')[0];
    }

    formatDateForFile(date) {
        return this.formatDateForInput(date);
    }

    async loadAvailableDates() {
        try {
            const response = await fetch('dates.json');
            if (response.ok) {
                this.availableDates = await response.json();
            }
        } catch (e) {
            console.log('No dates.json found, will try loading data directly');
            this.availableDates = null;
        }
    }

    async loadEPGData() {
        this.showLoading(true);
        this.channels.clear();
        this.programs = [];

        const dateStr = this.formatDateForFile(this.selectedDate);
        const year = this.selectedDate.getFullYear();
        
        const paths = [
            `../archive/${year}/${dateStr}.xml`,
            `archive/${year}/${dateStr}.xml`,
            `data/${year}/${dateStr}.xml`
        ];

        let loaded = false;
        for (const path of paths) {
            try {
                const response = await fetch(path);
                if (response.ok) {
                    const xmlText = await response.text();
                    this.parseXMLTV(xmlText);
                    loaded = true;
                    break;
                }
            } catch (e) {
                continue;
            }
        }

        if (!loaded) {
            this.showEmptyState(`Aucune donnée pour le ${this.formatDisplayDate(this.selectedDate)}`);
        } else {
            this.renderChannelList();
            this.renderTimeHeader();
            this.renderEPGGrid();
        }

        this.showLoading(false);
    }

    parseXMLTV(xmlText) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(xmlText, 'text/xml');

        const channelElements = doc.querySelectorAll('channel');
        channelElements.forEach(ch => {
            const id = ch.getAttribute('id');
            const displayName = ch.querySelector('display-name')?.textContent || id;
            const icon = ch.querySelector('icon')?.getAttribute('src') || null;
            
            this.channels.set(id, {
                id,
                displayName,
                icon,
                programs: []
            });
        });

        const programElements = doc.querySelectorAll('programme');
        programElements.forEach(prog => {
            const channelId = prog.getAttribute('channel');
            const startStr = prog.getAttribute('start');
            const stopStr = prog.getAttribute('stop');
            
            const program = {
                channel: channelId,
                start: this.parseXMLTVDate(startStr),
                stop: this.parseXMLTVDate(stopStr),
                title: prog.querySelector('title')?.textContent || 'Sans titre',
                description: prog.querySelector('desc')?.textContent || '',
                category: prog.querySelector('category')?.textContent || '',
                icon: prog.querySelector('icon')?.getAttribute('src') || null
            };

            this.programs.push(program);

            const channel = this.channels.get(channelId);
            if (channel) {
                channel.programs.push(program);
            }
        });

        this.channels.forEach(channel => {
            channel.programs.sort((a, b) => a.start - b.start);
        });

        this.filteredChannels = Array.from(this.channels.values())
            .sort((a, b) => a.displayName.localeCompare(b.displayName));
    }

    parseXMLTVDate(dateStr) {
        if (!dateStr) return null;
        
        // Format: 20250106002000 +0100
        const match = dateStr.match(/^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})\s*([+-]\d{4})?/);
        if (!match) return null;

        const [, year, month, day, hour, minute, second, timezone] = match;
        
        // Si un fuseau horaire est présent, créer une date UTC puis ajuster
        if (timezone) {
            const tzHours = parseInt(timezone.substring(1, 3));
            const tzMinutes = parseInt(timezone.substring(3, 5));
            const tzOffsetMinutes = (timezone[0] === '+' ? 1 : -1) * (tzHours * 60 + tzMinutes);
            
            // Créer la date en UTC
            const utcDate = Date.UTC(year, month - 1, day, hour, minute, second);
            // Soustraire l'offset du fuseau horaire pour obtenir l'UTC réel
            return new Date(utcDate - tzOffsetMinutes * 60000);
        }
        
        // Sinon, créer une date en heure locale
        return new Date(year, month - 1, day, hour, minute, second);
    }

    formatDisplayDate(date) {
        return date.toLocaleDateString('fr-FR', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
    }

    formatTime(date) {
        if (!date) return '';
        return date.toLocaleTimeString('fr-FR', {
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    navigateDay(delta) {
        const newDate = new Date(this.selectedDate);
        newDate.setDate(newDate.getDate() + delta);
        this.selectedDate = newDate;
        this.datePicker.value = this.formatDateForInput(newDate);
        this.loadEPGData();
    }

    onDateChange() {
        const [year, month, day] = this.datePicker.value.split('-').map(Number);
        this.selectedDate = new Date(year, month - 1, day, 0, 0, 0, 0);
        this.loadEPGData();
    }

    filterChannels() {
        const query = this.channelSearch.value.toLowerCase().trim();
        
        if (!query) {
            this.filteredChannels = Array.from(this.channels.values())
                .sort((a, b) => a.displayName.localeCompare(b.displayName));
        } else {
            this.filteredChannels = Array.from(this.channels.values())
                .filter(ch => ch.displayName.toLowerCase().includes(query))
                .sort((a, b) => a.displayName.localeCompare(b.displayName));
        }

        this.renderChannelList();
        this.renderEPGGrid();
    }

    renderChannelList() {
        this.channelCount.textContent = this.filteredChannels.length;

        if (this.filteredChannels.length === 0) {
            this.channelList.innerHTML = '<div class="loading">Aucune chaîne trouvée</div>';
            return;
        }

        this.channelList.innerHTML = this.filteredChannels.map(channel => `
            <div class="channel-item" data-channel-id="${channel.id}">
                ${channel.icon 
                    ? `<img src="${channel.icon}" alt="" class="channel-icon" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"><div class="channel-icon-placeholder" style="display:none">${channel.displayName.charAt(0)}</div>`
                    : `<div class="channel-icon-placeholder">${channel.displayName.charAt(0)}</div>`
                }
                <span class="channel-name">${channel.displayName}</span>
            </div>
        `).join('');

        this.channelList.querySelectorAll('.channel-item').forEach(item => {
            item.addEventListener('click', () => {
                const channelId = item.dataset.channelId;
                this.scrollToChannel(channelId);
            });
        });
    }

    renderTimeHeader() {
        let html = '';
        for (let hour = this.dayStartHour; hour < this.dayEndHour; hour++) {
            html += `<div class="time-slot">${hour.toString().padStart(2, '0')}:00</div>`;
        }
        this.timeHeader.innerHTML = html;
    }

    renderEPGGrid() {
        if (this.filteredChannels.length === 0) {
            this.epgGrid.innerHTML = `
                <div class="empty-state">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <rect x="2" y="7" width="20" height="15" rx="2" ry="2"></rect>
                        <polyline points="17 2 12 7 7 2"></polyline>
                    </svg>
                    <h3>Aucune chaîne</h3>
                    <p>Aucune chaîne ne correspond à votre recherche</p>
                </div>
            `;
            return;
        }

        const totalMinutes = (this.dayEndHour - this.dayStartHour) * 60;
        const gridWidth = totalMinutes * this.pixelsPerMinute;

        let html = '';
        this.filteredChannels.forEach(channel => {
            html += `
                <div class="channel-row" id="channel-${channel.id}">
                    <div class="channel-row-header">
                        ${channel.icon 
                            ? `<img src="${channel.icon}" alt="" onerror="this.style.display='none'">`
                            : ''
                        }
                        <span class="channel-row-name">${channel.displayName}</span>
                    </div>
                    <div class="channel-programs" style="width: ${gridWidth}px; min-width: ${gridWidth}px;">
                        ${this.renderChannelPrograms(channel)}
                    </div>
                </div>
            `;
        });

        this.epgGrid.innerHTML = html;

        this.epgGrid.querySelectorAll('.program').forEach(prog => {
            prog.addEventListener('click', () => {
                const programData = JSON.parse(prog.dataset.program);
                this.showProgramDetails(programData);
            });
        });
    }

    renderChannelPrograms(channel) {
        const dayStart = new Date(this.selectedDate);
        dayStart.setHours(this.dayStartHour, 0, 0, 0);
        
        const dayEnd = new Date(this.selectedDate);
        dayEnd.setHours(this.dayEndHour, 0, 0, 0);

        return channel.programs
            .filter(prog => {
                return prog.start < dayEnd && prog.stop > dayStart;
            })
            .map(prog => {
                const startTime = Math.max(prog.start, dayStart);
                const endTime = Math.min(prog.stop, dayEnd);
                
                const startMinutes = (startTime - dayStart) / 60000;
                const duration = (endTime - startTime) / 60000;
                
                const left = startMinutes * this.pixelsPerMinute;
                const width = Math.max(duration * this.pixelsPerMinute - 2, 30);

                const categoryClass = this.getCategoryClass(prog.category);

                const programData = {
                    title: prog.title,
                    description: prog.description,
                    category: prog.category,
                    icon: prog.icon,
                    channelName: channel.displayName,
                    channelIcon: channel.icon,
                    start: prog.start.toISOString(),
                    stop: prog.stop.toISOString()
                };

                return `
                    <div class="program ${categoryClass}" 
                         style="left: ${left}px; width: ${width}px;"
                         data-program='${JSON.stringify(programData).replace(/'/g, "&#39;")}'>
                        <div class="program-title">${this.escapeHtml(prog.title)}</div>
                        <div class="program-time">${this.formatTime(prog.start)} - ${this.formatTime(prog.stop)}</div>
                    </div>
                `;
            })
            .join('');
    }

    getCategoryClass(category) {
        if (!category) return '';
        const cat = category.toLowerCase();
        
        if (cat.includes('film') || cat.includes('cinéma')) return 'category-film';
        if (cat.includes('sport')) return 'category-sport';
        if (cat.includes('info') || cat.includes('journal') || cat.includes('actualité')) return 'category-info';
        if (cat.includes('série') || cat.includes('feuilleton')) return 'category-serie';
        if (cat.includes('divertissement') || cat.includes('jeu') || cat.includes('humour')) return 'category-divertissement';
        if (cat.includes('jeunesse') || cat.includes('dessin') || cat.includes('enfant')) return 'category-jeunesse';
        if (cat.includes('documentaire') || cat.includes('découverte') || cat.includes('magazine')) return 'category-documentaire';
        
        return '';
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    scrollToChannel(channelId) {
        const channelRow = document.getElementById(`channel-${channelId}`);
        if (channelRow) {
            channelRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
            channelRow.style.animation = 'none';
            channelRow.offsetHeight;
            channelRow.style.animation = 'highlight 1s ease';
        }
    }

    showProgramDetails(program) {
        document.getElementById('modal-title').textContent = program.title;
        document.getElementById('modal-channel').textContent = program.channelName;
        
        const modalIcon = document.getElementById('modal-icon');
        if (program.icon) {
            modalIcon.src = program.icon;
            modalIcon.style.display = 'block';
        } else if (program.channelIcon) {
            modalIcon.src = program.channelIcon;
            modalIcon.style.display = 'block';
        } else {
            modalIcon.style.display = 'none';
        }

        const start = new Date(program.start);
        const stop = new Date(program.stop);
        const duration = Math.round((stop - start) / 60000);
        document.getElementById('modal-time').textContent = 
            `${this.formatTime(start)} - ${this.formatTime(stop)} (${duration} min)`;

        const categoryEl = document.getElementById('modal-category');
        if (program.category) {
            categoryEl.textContent = program.category;
            categoryEl.style.display = 'inline-block';
        } else {
            categoryEl.style.display = 'none';
        }

        document.getElementById('modal-description').textContent = 
            program.description || 'Aucune description disponible.';

        this.modal.classList.add('active');
    }

    closeModal() {
        this.modal.classList.remove('active');
    }

    showLoading(show) {
        this.loading.style.display = show ? 'flex' : 'none';
    }

    showEmptyState(message) {
        this.channelList.innerHTML = '<div class="loading">Aucune donnée</div>';
        this.channelCount.textContent = '0';
        this.epgGrid.innerHTML = `
            <div class="empty-state">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="8" x2="12" y2="12"></line>
                    <line x1="12" y1="16" x2="12.01" y2="16"></line>
                </svg>
                <h3>Données non disponibles</h3>
                <p>${message}</p>
            </div>
        `;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new EPGViewer();
});
