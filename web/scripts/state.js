/* =====================================================================
   MittiMandi Mobile App — Reactive State Store & Session Management
   ===================================================================== */

import { localDb } from './db.js';
import { DEMO_MODE, warnDemoFallback } from '../config.js';

class StateStore {
  constructor() {
    this.listeners = new Map();

    const storedAccessToken = localStorage.getItem('mm_access_token') || 'demo-jwt-token-98213812';
    const storedRefreshToken = localStorage.getItem('mm_refresh_token') || 'demo-refresh-token-98213812';

    if (DEMO_MODE) {
      warnDemoFallback('StateStore', 'DEMO_MODE is ACTIVE — hardcoded mock data loaded into state store');
    }

    this.state = {
      theme: 'dark',
      deviceMode: 'phone', // 'phone' or 'fullscreen'
      currentScreen: 'splash',
      activeTab: 'home',
      
      // User & Auth Session (Stored & Retained for 401 Refreshes)
      session: {
        accessToken: storedAccessToken,
        refreshToken: storedRefreshToken,
        tokenType: 'bearer',
        expiresAt: Date.now() + 900000
      },

      user: {
        phone: '9876543210',
        name: 'Ramesh Patel',
        role: 'farmer', // farmer, fpo, buyer, transporter
        language: 'hi', // hi, en, mr, pa, gu
        location: 'Khargone, Madhya Pradesh',
        fpo: 'Nimar Kisan Producer Co. Ltd.',
        verified: true,
        rating: 4.8
      },

      // Live Mandi Tickers (Empty by default; populated from API or empty state)
      mandiPrices: DEMO_MODE ? [
        { crop: 'Wheat (Sharbati)', variety: 'Lokwan', mandi: 'Indore APMC', price: 2850, delta: '+3.8%', trend: 'up' },
        { crop: 'Soyabean (Yellow)', variety: 'JS-9560', mandi: 'Ujjain APMC', price: 4720, delta: '+1.4%', trend: 'up' },
        { crop: 'Chana (Desi)', variety: 'JG-11', mandi: 'Dewas APMC', price: 5950, delta: '-0.8%', trend: 'down' },
        { crop: 'Mustard (Bold)', variety: 'Pusa Bold', mandi: 'Morena APMC', price: 5400, delta: '+2.1%', trend: 'up' }
      ] : [],

      // Harvest Lots Catalog (Populated from Local Database)
      lots: [],

      // Active Negotiations (Null by default)
      negotiation: DEMO_MODE ? {
        lotId: 'LOT-MP-2026-081',
        buyerName: 'ITC Agri Business Ltd.',
        buyerLocation: 'Indore Hub',
        initialBid: 2850,
        currentOffer: 2920,
        farmerTarget: 2950,
        priceLockStatus: 'Active',
        quantityLock: 100, // Quintals
        history: [
          { sender: 'buyer', price: 2850, note: 'Initial procurement bid for 100 Qtl delivery at Indore warehouse.' },
          { sender: 'farmer', price: 2950, note: 'Grain quality certified Grade A, moisture under 11%.' },
          { sender: 'buyer', price: 2920, note: 'Revised offer with 48hr price lock guarantee.' }
        ]
      } : null,

      // Transport Bookings (ONDC Logistics Aggregation - Empty by default)
      transports: DEMO_MODE ? [
        { id: 'TRP-01', provider: 'TruckSe Logistics (ONDC)', vehicle: '14ft Eicher (4 Ton)', ratePerKm: 34, eta: '45 mins', rating: 4.7, totalEstimate: 2380 },
        { id: 'TRP-02', provider: 'Gramin Transport Hub', vehicle: 'Mahindra Bolero Maxi (2 Ton)', ratePerKm: 28, eta: '25 mins', rating: 4.9, totalEstimate: 1960 },
        { id: 'TRP-03', provider: 'Kisan Vahan Sewa', vehicle: 'Tata 407 (3.5 Ton)', ratePerKm: 32, eta: '1 hr', rating: 4.6, totalEstimate: 2240 }
      ] : [],
      selectedTransport: DEMO_MODE ? 'TRP-01' : null,

      // Cold Storage Warehouses (Empty by default)
      warehouses: DEMO_MODE ? [
        { id: 'WH-01', name: 'Nimar Central Cold Storage (WDRA)', distance: '12 km', capacityLeft: '450 MT', monthlyRatePerQtl: 28, rating: 4.8 },
        { id: 'WH-02', name: 'Indore Agri Logistics Park', distance: '38 km', capacityLeft: '1,200 MT', monthlyRatePerQtl: 24, rating: 4.9 }
      ] : [],

      // Offline Synchronization State
      isOnline: navigator.onLine,
      syncState: {
        status: navigator.onLine ? 'idle' : 'offline',
        detail: navigator.onLine ? 'Connected. Ready to sync.' : 'Offline. Mutations queued in local IndexedDB.',
        lastUpdated: Date.now()
      },
      pendingSyncCount: 0,
      conflicts: []
    };
  }

  get(key) {
    return this.state[key];
  }

  set(key, value) {
    this.state[key] = value;
    this.notify(key, value);
  }

  update(key, fn) {
    const newVal = fn(this.state[key]);
    this.set(key, newVal);
  }

  subscribe(key, callback) {
    if (!this.listeners.has(key)) {
      this.listeners.set(key, new Set());
    }
    this.listeners.get(key).add(callback);
    return () => this.listeners.get(key).delete(callback);
  }

  notify(key, value) {
    if (this.listeners.has(key)) {
      for (const callback of this.listeners.get(key)) {
        callback(value, this.state);
      }
    }
    if (this.listeners.has('*')) {
      for (const callback of this.listeners.get('*')) {
        callback(key, value, this.state);
      }
    }
  }

  // -------------------------------------------------------------------
  // Load State from Local Database (Single Source of Truth)
  // -------------------------------------------------------------------

  async refreshFromLocalDb() {
    try {
      const lots = await localDb.getAll('lots');
      if (lots && lots.length > 0) {
        this.set('lots', lots);
      } else if (DEMO_MODE) {
        warnDemoFallback('lots', 'DEMO_MODE is ACTIVE — seeding demo lots into localDb');
        // Seed initial lots into Local Database if empty in DEMO_MODE
        const initialLots = [
          {
            id: 'LOT-MP-2026-081',
            crop: 'Wheat (Sharbati)',
            variety: 'Premium C-306',
            quantity: 120,
            quantity_mt: 12.0,
            pricePerQtl: 2950,
            grade: 'Grade A',
            moisture: '10.8%',
            foreignMatter: '0.4%',
            damagedGrains: '0.8%',
            assayScore: 94.2,
            hmacSeal: '0x8f2a...91ce',
            harvestDate: '2026-03-20',
            status: 'registered',
            highestBid: 2920,
            bidsCount: 4,
            farmer: 'Ramesh Patel',
            created_at: 1727280100000,
            updated_at: 1727280100000,
            deleted_at: null,
            _syncStatus: 'synced'
          },
          {
            id: 'LOT-MP-2026-094',
            crop: 'Soyabean (Yellow)',
            variety: 'JS-335 Organic',
            quantity: 85,
            quantity_mt: 8.5,
            pricePerQtl: 4850,
            grade: 'Grade A',
            moisture: '11.2%',
            foreignMatter: '0.6%',
            damagedGrains: '1.1%',
            assayScore: 91.5,
            hmacSeal: '0x4c1e...b730',
            harvestDate: '2026-03-18',
            status: 'draft',
            highestBid: 4800,
            bidsCount: 6,
            farmer: 'Ramesh Patel',
            created_at: 1727283500000,
            updated_at: 1727283500000,
            deleted_at: null,
            _syncStatus: 'synced'
          }
        ];

        for (const lot of initialLots) {
          await localDb.put('lots', lot, true);
        }
        this.set('lots', initialLots);
      } else {
        this.set('lots', []);
      }

      const outboxCount = await localDb.getOutboxCount();
      this.set('pendingSyncCount', outboxCount);

      const conflicts = await localDb.getConflicts();
      this.set('conflicts', conflicts);
    } catch (e) {
      console.error('Error refreshing from local database:', e);
    }
  }
}

export const store = new StateStore();
