/* =====================================================================
   MittiMandi Screen: Authentication & Onboarding (AUTH-01 to AUTH-05)
   Migrated onto shared component library (F1 Foundation)
   ===================================================================== */

import { store } from '../state.js';
import { api } from '../api.js';
import { renderBadge } from '../components/badge.js';
import { renderButton } from '../components/button.js';
import { renderCard } from '../components/card.js';
import { renderPhoneInput } from '../components/input.js';

export function renderSplash() {
  return `
    <div class="splash-screen">
      <div class="splash-top-bar">
        ${renderBadge('STITCH MOBILE v2.4', 'primary')}
      </div>

      <div class="splash-art">
        <div class="splash-glow-ring"></div>
        <div class="splash-icon">🌾</div>
      </div>

      <div class="splash-title-group">
        <h1 class="headline-lg splash-title">MittiMandi</h1>
        <div class="brand-subtitle">मिट्टी से मंडी तक · Direct Farmer Market</div>
        <p class="splash-tagline">
          Empowering Farmers with Real-Time Mandi AI, Transparent Trades & Instant ONDC Settlements
        </p>

        <div class="splash-pills">
          ${renderBadge('✓ 0% Commission', 'success')}
          ${renderBadge('✓ AI Assay Quality', 'primary')}
          ${renderBadge('✓ Escrow Protected', 'tertiary')}
        </div>
      </div>

      <div class="splash-actions">
        ${renderButton({
          text: 'Get Started / शुरू करें →',
          variant: 'primary',
          size: 'lg',
          isBlock: true,
          action: 'nav',
          screen: 'auth-language'
        })}
        ${renderButton({
          text: 'Skip to Demo Dashboard ⚡',
          variant: 'ghost',
          size: 'sm',
          action: 'nav',
          screen: 'dashboard'
        })}
      </div>
    </div>
  `;
}

export function renderLanguage() {
  const currentLang = store.get('user').language;
  const languages = [
    { code: 'hi', native: 'हिन्दी', english: 'Hindi', audio: '🔊' },
    { code: 'en', native: 'English', english: 'English', audio: '🔊' },
    { code: 'mr', native: 'मराठी', english: 'Marathi', audio: '🔊' },
    { code: 'pa', native: 'ਪੰਜਾਬੀ', english: 'Punjabi', audio: '🔊' },
    { code: 'gu', native: 'ગુજરાતી', english: 'Gujarati', audio: '🔊' },
    { code: 'te', native: 'తెలుగు', english: 'Telugu', audio: '🔊' }
  ];

  return `
    <div class="screen-content">
      <div>
        ${renderBadge('AUTH-02 · SELECT LANGUAGE', 'primary')}
        <h2 class="headline-md mt-sm">अपनी भाषा चुनें</h2>
        <p class="caption text-secondary">Choose your preferred language for voice advisory and transactions.</p>
      </div>

      <div class="language-grid">
        ${languages.map(l => `
          <div class="lang-btn ${l.code === currentLang ? 'active' : ''}" data-action="set-lang" data-lang="${l.code}">
            <span class="lang-speaker">${l.audio}</span>
            <span class="lang-native">${l.native}</span>
            <span class="lang-english">${l.english}</span>
          </div>
        `).join('')}
      </div>

      <div class="auth-action-footer">
        ${renderButton({
          text: 'Continue / आगे बढ़ें →',
          variant: 'primary',
          size: 'lg',
          isBlock: true,
          action: 'nav',
          screen: 'auth-login'
        })}
      </div>
    </div>
  `;
}

export function renderLogin() {
  const phone = store.get('user').phone;
  const cardContent = `
    ${renderPhoneInput({
      id: 'login-phone',
      value: phone,
      label: 'Phone Number',
      helper: 'WhatsApp / SMS OTP'
    })}
    <div class="auth-consent-row">
      <input type="checkbox" id="dpdp-consent" checked class="form-checkbox">
      <label for="dpdp-consent">
        I consent to DPDP Act 2023 verified identity verification and agree to the 
        <span class="text-accent">Terms of Agricultural Trade</span>.
      </label>
    </div>
  `;

  return `
    <div class="screen-content">
      <div>
        ${renderBadge('AUTH-03 · MOBILE LOGIN', 'primary')}
        <h2 class="headline-md mt-sm">Enter Mobile Number</h2>
        <p class="caption text-secondary">We will send a 6-digit verification code to your phone.</p>
      </div>

      ${renderCard({ content: cardContent, extraClasses: 'mt-md' })}

      <div class="auth-action-footer">
        ${renderButton({
          text: 'Send OTP / ओटीपी प्राप्त करें',
          variant: 'primary',
          size: 'lg',
          isBlock: true,
          action: 'send-otp'
        })}
      </div>
    </div>
  `;
}

export function renderOtp() {
  const phone = store.get('user').phone;
  const cardContent = `
    <span class="caption text-muted">Enter 6-digit Code</span>
    <div class="otp-grid">
      <input type="text" maxlength="1" class="otp-digit" value="1">
      <input type="text" maxlength="1" class="otp-digit" value="2">
      <input type="text" maxlength="1" class="otp-digit" value="3">
      <input type="text" maxlength="1" class="otp-digit" value="4">
      <input type="text" maxlength="1" class="otp-digit" value="5">
      <input type="text" maxlength="1" class="otp-digit" value="6">
    </div>

    <div class="auth-resend-row">
      <span class="auth-resend-timer">Resend code in 00:48s</span>
      ${renderButton({
        text: 'Fill Demo OTP',
        variant: 'ghost',
        size: 'sm',
        extraClasses: 'text-accent',
        action: 'fill-demo-otp'
      })}
    </div>
  `;

  return `
    <div class="screen-content">
      <div>
        ${renderBadge('AUTH-04 · OTP VERIFICATION', 'primary')}
        <h2 class="headline-md mt-sm">Verify Security Code</h2>
        <p class="caption text-secondary">Sent via SMS to <strong>+91 ${phone}</strong></p>
      </div>

      ${renderCard({ content: cardContent, extraClasses: 'text-center mt-md' })}

      <div class="auth-action-footer">
        ${renderButton({
          text: 'Verify & Continue / सत्यापित करें',
          variant: 'primary',
          size: 'lg',
          isBlock: true,
          action: 'verify-otp'
        })}
      </div>
    </div>
  `;
}

export function renderRole() {
  const currentRole = store.get('user').role;
  const roles = [
    { id: 'farmer', title: 'Farmer / किसान', subtitle: 'Sell harvest lots directly to institutional buyers', icon: '🌾' },
    { id: 'fpo', title: 'FPO Representative', subtitle: 'Aggregate produce, manage members & bulk deals', icon: '🏢' },
    { id: 'buyer', title: 'Commodity Buyer', subtitle: 'Discover inspected grain lots with price locks', icon: '💼' },
    { id: 'transporter', title: 'ONDC Logistics', subtitle: 'Provide verified farm-to-warehouse transit', icon: '🚚' }
  ];

  return `
    <div class="screen-content">
      <div>
        ${renderBadge('AUTH-05 · ROLE SELECTION', 'primary')}
        <h2 class="headline-md mt-sm">Select Your Profile</h2>
        <p class="caption text-secondary">Choose your active role on the MittiMandi exchange network.</p>
      </div>

      <div class="selectable-grid">
        ${roles.map(r => `
          <div class="selectable-card ${r.id === currentRole ? 'selected' : ''}" data-action="set-role" data-role="${r.id}">
            <div class="selectable-card-icon">${r.icon}</div>
            <div class="flex-col">
              <span class="selectable-card-title">${r.title}</span>
              <span class="selectable-card-subtitle">${r.subtitle}</span>
            </div>
          </div>
        `).join('')}
      </div>

      <div class="auth-action-footer">
        ${renderButton({
          text: 'Enter Marketplace / मंडी में प्रवेश करें →',
          variant: 'primary',
          size: 'lg',
          isBlock: true,
          action: 'nav',
          screen: 'dashboard'
        })}
      </div>
    </div>
  `;
}
