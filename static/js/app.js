/* Airteal Payment Bank - Interactive Features */

document.addEventListener("DOMContentLoaded", () => {
    // Auto-close flash messages after 5 seconds
    const flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(message => {
        setTimeout(() => {
            message.style.animation = 'fadeOut 0.3s ease forwards';
            setTimeout(() => message.remove(), 300);
        }, 5000);
    });
    
    // Mobile menu toggle
    const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
    const sidebar = document.querySelector('.sidebar');
    if (mobileMenuBtn) {
        mobileMenuBtn.addEventListener('click', () => {
            sidebar.classList.toggle('open');
        });
    }
    
    // Close mobile menu when a link is clicked
    const sidebarLinks = document.querySelectorAll('.sidebar a');
    sidebarLinks.forEach(link => {
        link.addEventListener('click', () => {
            sidebar.classList.remove('open');
        });
    });

    // Animated Counter for Balance
    const balanceElem = document.getElementById("animated-balance");
    if (balanceElem) {
        fetchBalance(balanceElem);
        // Auto refresh every 10 seconds
        setInterval(() => fetchBalance(balanceElem), 10000);
    }

    // Form Loading Spinner
    const forms = document.querySelectorAll("form");
    const loader = document.getElementById("loader");

    forms.forEach(form => {
        form.addEventListener("submit", () => {
            if (loader && form.checkValidity()) {
                loader.classList.add("active");
            }
        });
    });

    // Play Success Sound on certain pages
    const successElement = document.getElementById("success-anim");
    if (successElement) {
        playSuccessSound();
    }
    
    // Form validation on input
    const inputs = document.querySelectorAll('input[required], textarea[required]');
    inputs.forEach(input => {
        input.addEventListener('blur', () => {
            validateField(input);
        });
    });
});

function fetchBalance(element) {
    fetch('/api/get-balance')
        .then(response => response.json())
        .then(data => {
            if (data.balance !== undefined) {
                animateValue(element, parseFloat(element.innerText.replace(/,/g, '')) || 0, data.balance, 1000);
            }
        })
        .catch(err => console.error("Error fetching balance", err));
}

function animateValue(obj, start, end, duration) {
    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        
        // Easing function outQuart
        const easeOut = 1 - Math.pow(1 - progress, 4);
        const current = start + (end - start) * easeOut;
        
        obj.innerHTML = current.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        if (progress < 1) {
            window.requestAnimationFrame(step);
        } else {
            obj.innerHTML = end.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        }
    };
    window.requestAnimationFrame(step);
}

// Validate individual field
function validateField(field) {
    const formGroup = field.closest('.form-group');
    if (!formGroup) return true;
    
    let isValid = true;
    
    if (field.hasAttribute('required') && !field.value.trim()) {
        isValid = false;
    } else if (field.type === 'email' && field.value && !isValidEmail(field.value)) {
        isValid = false;
    }
    
    if (isValid) {
        formGroup.classList.remove('error');
    } else {
        formGroup.classList.add('error');
    }
    
    return isValid;
}

// Validate form
function validateForm(formElement) {
    const inputs = formElement.querySelectorAll('[required]');
    let isValid = true;
    
    inputs.forEach(input => {
        if (!validateField(input)) {
            isValid = false;
        }
    });
    
    return isValid;
}

function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

// Show loader
function showLoader() {
    const loader = document.getElementById('loader');
    if (loader) {
        loader.classList.add('active');
    }
}

// Hide loader
function hideLoader() {
    const loader = document.getElementById('loader');
    if (loader) {
        loader.classList.remove('active');
    }
}

// Copy to clipboard
function copyToClipboard(text, message = 'Copied!') {
    navigator.clipboard.writeText(text).then(() => {
        showFlashMessage(message, 'success');
    }).catch(err => {
        console.error('Failed to copy:', err);
    });
}

// Show flash message
function showFlashMessage(message, type = 'info') {
    const container = document.createElement('div');
    container.className = `flash-message flash-${type}`;
    container.textContent = message;
    document.body.appendChild(container);
    
    setTimeout(() => {
        container.style.animation = 'fadeOut 0.3s ease forwards';
        setTimeout(() => container.remove(), 300);
    }, 5000);
}

// Format currency
function formatCurrency(amount, currency = 'USD') {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: currency,
    }).format(amount);
}

// Format date
function formatDate(date) {
    return new Intl.DateTimeFormat('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    }).format(new Date(date));
}

function playSuccessSound() {
    // A simple short high-pitched ping using Web Audio API
    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioCtx.createOscillator();
        const gainNode = audioCtx.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioCtx.destination);
        
        oscillator.type = 'sine';
        oscillator.frequency.setValueAtTime(880, audioCtx.currentTime); // A5
        oscillator.frequency.exponentialRampToValueAtTime(1760, audioCtx.currentTime + 0.1); // A6
        
        gainNode.gain.setValueAtTime(0.5, audioCtx.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.5);
        
        oscillator.start();
        oscillator.stop(audioCtx.currentTime + 0.5);
    } catch(e) {
        console.log("Audio not supported or blocked");
    }
}

// Sidebar toggle for mobile
function toggleSidebar() {
    const sidebar = document.querySelector('.sidebar');
    if (sidebar) {
        sidebar.classList.toggle('open');
    }
}

// Fade out animation
const style = document.createElement('style');
style.textContent = `
    @keyframes fadeOut {
        to {
            opacity: 0;
            transform: translateY(-10px);
        }
    }
`;
document.head.appendChild(style);
