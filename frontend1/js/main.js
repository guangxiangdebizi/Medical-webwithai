/**
 * Dolphin Trinity AI™ - Main JavaScript
 * Handles common functionality across all pages
 */

// API Configuration
const API_BASE = '/trinity-api';

// Scroll reveal animation
function initScrollReveal() {
    const revealElements = document.querySelectorAll('.reveal');
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('active');
            }
        });
    }, {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    });
    
    revealElements.forEach(el => observer.observe(el));
}

// Smooth scroll for anchor links
function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
}

// Navigation scroll effect
function initNavScroll() {
    const nav = document.querySelector('.nav');
    let lastScrollY = window.scrollY;
    
    window.addEventListener('scroll', () => {
        const currentScrollY = window.scrollY;
        
        if (currentScrollY > 100) {
            nav.style.background = 'rgba(10, 14, 23, 0.95)';
        } else {
            nav.style.background = 'rgba(10, 14, 23, 0.85)';
        }
        
        lastScrollY = currentScrollY;
    });
}

// Particle effect for hero section
function initParticles() {
    const hero = document.querySelector('.hero');
    if (!hero) return;
    
    const colors = ['var(--blue-primary)', 'var(--amber-primary)', 'var(--teal-primary)'];
    
    setInterval(() => {
        const particle = document.createElement('div');
        particle.className = 'particle';
        particle.style.left = Math.random() * 100 + '%';
        particle.style.bottom = '0';
        particle.style.background = colors[Math.floor(Math.random() * colors.length)];
        particle.style.boxShadow = `0 0 10px ${particle.style.background}`;
        particle.style.animationDuration = (3 + Math.random() * 2) + 's';
        
        hero.appendChild(particle);
        
        setTimeout(() => particle.remove(), 5000);
    }, 300);
}

// Agent card hover effects
function initAgentCards() {
    const cards = document.querySelectorAll('.agent-card');
    
    cards.forEach(card => {
        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            card.style.setProperty('--mouse-x', `${x}px`);
            card.style.setProperty('--mouse-y', `${y}px`);
        });
    });
}

// Counter animation for value section
function initCounters() {
    const counters = document.querySelectorAll('.value-number');
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const el = entry.target;
                const text = el.textContent;
                
                // Skip if already animated or is not a number
                if (el.dataset.animated || !/^\d+/.test(text)) return;
                
                el.dataset.animated = 'true';
                
                const match = text.match(/^(\d+)(.*)$/);
                if (match) {
                    const target = parseInt(match[1]);
                    const suffix = match[2];
                    let current = 0;
                    const increment = target / 50;
                    const duration = 1500;
                    const stepTime = duration / 50;
                    
                    const timer = setInterval(() => {
                        current += increment;
                        if (current >= target) {
                            current = target;
                            clearInterval(timer);
                        }
                        el.textContent = Math.floor(current) + suffix;
                    }, stepTime);
                }
            }
        });
    }, { threshold: 0.5 });
    
    counters.forEach(counter => observer.observe(counter));
}

// Typing effect for signature words
function initTypingEffect() {
    const signatures = document.querySelectorAll('.agent-word');
    
    signatures.forEach(sig => {
        const text = sig.textContent;
        sig.textContent = '';
        sig.style.visibility = 'visible';
        
        let i = 0;
        const typeWriter = () => {
            if (i < text.length) {
                sig.textContent += text.charAt(i);
                i++;
                setTimeout(typeWriter, 100);
            }
        };
        
        // Start typing when element is in view
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting && !sig.dataset.typed) {
                    sig.dataset.typed = 'true';
                    setTimeout(typeWriter, 500);
                }
            });
        }, { threshold: 0.5 });
        
        observer.observe(sig);
    });
}

// File upload helper
function setupFileUpload(dropZoneId, fileInputId, onFileSelected) {
    const dropZone = document.getElementById(dropZoneId);
    const fileInput = document.getElementById(fileInputId);
    const selectBtn = document.getElementById('selectFileBtn');
    
    if (!dropZone || !fileInput) return;
    
    // Click to select
    if (selectBtn) {
        selectBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            fileInput.click();
        });
    }
    
    dropZone.addEventListener('click', () => fileInput.click());
    
    // Drag and drop
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
        });
    });
    
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.add('dragover');
        });
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.remove('dragover');
        });
    });
    
    dropZone.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0 && files[0].type === 'application/pdf') {
            onFileSelected(files[0]);
        }
    });
    
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            onFileSelected(e.target.files[0]);
        }
    });
}

// Format file size
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Show toast notification
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed;
        bottom: 24px;
        right: 24px;
        padding: 16px 24px;
        background: var(--bg-card);
        border-radius: 12px;
        border: 1px solid ${type === 'error' ? 'var(--red-accent)' : type === 'success' ? 'var(--green-accent)' : 'var(--blue-primary)'};
        color: var(--text-primary);
        font-size: 0.9rem;
        z-index: 9999;
        animation: slideIn 0.3s ease;
    `;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Initialize everything on DOM load
document.addEventListener('DOMContentLoaded', () => {
    initScrollReveal();
    initSmoothScroll();
    initNavScroll();
    initAgentCards();
    initCounters();
    
    // Only init particles on home page
    if (document.querySelector('.hero')) {
        initParticles();
    }
});

// Add CSS for toast animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
`;
document.head.appendChild(style);


