/**
 * Home page JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('Home page loaded');
    
    // Check if user is authenticated and show appropriate content
    checkAuthenticationStatus();
    
    // Initialize any home page specific features
    initializeHomeFeatures();
});

/**
 * Check authentication status and update UI
 */
function checkAuthenticationStatus() {
    const userInfo = document.querySelector('[data-user-authenticated]');
    if (userInfo && userInfo.dataset.userAuthenticated === 'true') {
        console.log('User is authenticated');
        showAuthenticatedContent();
    } else {
        console.log('User is not authenticated');
        showGuestContent();
    }
}

/**
 * Show content for authenticated users
 */
function showAuthenticatedContent() {
    // Update welcome message if exists
    const welcomeMsg = document.querySelector('.welcome-message');
    if (welcomeMsg) {
        const userEmail = document.querySelector('[data-user-email]')?.dataset.userEmail;
        if (userEmail) {
            welcomeMsg.textContent = `Chào mừng, ${userEmail}!`;
        }
    }
    
    // Show dashboard link
    const dashboardLink = document.querySelector('.dashboard-link');
    if (dashboardLink) {
        dashboardLink.style.display = 'block';
    }
}

/**
 * Show content for guest users
 */
function showGuestContent() {
    // Show sign up prompts
    const signupPrompts = document.querySelectorAll('.signup-prompt');
    signupPrompts.forEach(prompt => {
        prompt.style.display = 'block';
    });
}

/**
 * Initialize home page features
 */
function initializeHomeFeatures() {
    // Smooth scrolling for anchor links
    const anchorLinks = document.querySelectorAll('a[href^="#"]');
    anchorLinks.forEach(link => {
        link.addEventListener('click', function(e) {
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
    
    // Add animation to feature cards
    animateFeatureCards();
}

/**
 * Animate feature cards on scroll
 */
function animateFeatureCards() {
    const cards = document.querySelectorAll('.feature-card');
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, {
        threshold: 0.1
    });
    
    cards.forEach(card => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(card);
    });
} 