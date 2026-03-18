<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div class="stats-grid">
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.budgetRange') }}</div>
          <div class="stat-value">
            ${{ data.min_budget.toLocaleString() }} – ${{ data.max_budget.toLocaleString() }}
          </div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.selectedItems') }}</div>
          <div class="stat-value">{{ data.total_selected_items }}</div>
        </div>
        <div class="stat-card warning">
          <div class="stat-label">{{ t('restocking.totalCost') }}</div>
          <div class="stat-value">
            {{ data.total_selected_cost.toLocaleString('en-US', { style: 'currency', currency: 'USD' }) }}
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.budgetSlider') }}</h3>
          <span class="budget-display">
            {{ budget.toLocaleString('en-US', { style: 'currency', currency: 'USD' }) }}
          </span>
        </div>
        <input
          type="range"
          class="budget-slider"
          :min="data.min_budget"
          :max="data.max_budget"
          v-model.number="budget"
        />
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">Recommendations ({{ data.recommendations.length }} items)</h3>
        </div>
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.itemName') }}</th>
                <th>{{ t('restocking.table.onHand') }}</th>
                <th>{{ t('restocking.table.forecasted') }}</th>
                <th>{{ t('restocking.table.gap') }}</th>
                <th>{{ t('restocking.table.restockQty') }}</th>
                <th>{{ t('restocking.table.unitCost') }}</th>
                <th>{{ t('restocking.table.totalCost') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="rec in data.recommendations"
                :key="rec.sku"
                :class="{ 'row-selected': rec.selected, 'row-dimmed': !rec.selected }"
              >
                <td><strong>{{ rec.sku }}</strong></td>
                <td>{{ rec.name }}</td>
                <td>{{ rec.quantity_on_hand }}</td>
                <td>{{ rec.forecasted_demand }}</td>
                <td>{{ rec.demand_gap }}</td>
                <td>{{ rec.restock_quantity }}</td>
                <td>{{ rec.unit_cost.toLocaleString('en-US', { style: 'currency', currency: 'USD' }) }}</td>
                <td>{{ rec.total_cost.toLocaleString('en-US', { style: 'currency', currency: 'USD' }) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="place-order-section">
          <button
            class="btn-primary"
            :disabled="!hasSelectedItems || submitting"
            @click="placeOrder"
          >
            {{ t('restocking.placeOrder') }}
          </button>
          <div class="success-message" v-if="successMessage">{{ successMessage }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue'
import { api } from '../api'
import { useFilters } from '../composables/useFilters'
import { useI18n } from '../composables/useI18n'

export default {
  name: 'Restocking',
  setup() {
    const { t } = useI18n()
    const { getCurrentFilters } = useFilters()

    const loading = ref(true)
    const error = ref(null)
    const data = ref(null)
    const budget = ref(50000)
    const submitting = ref(false)
    const successMessage = ref('')
    const debounceTimer = ref(null)

    const hasSelectedItems = computed(() => {
      if (!data.value) return false
      return data.value.recommendations.some(r => r.selected)
    })

    const loadRecommendations = async () => {
      try {
        loading.value = true
        error.value = null
        data.value = await api.getRestockingRecommendations(budget.value)
      } catch (err) {
        error.value = 'Failed to load restocking recommendations: ' + err.message
      } finally {
        loading.value = false
      }
    }

    // Watch budget with 300ms debounce
    watch(budget, () => {
      if (debounceTimer.value) clearTimeout(debounceTimer.value)
      debounceTimer.value = setTimeout(() => {
        loadRecommendations()
      }, 300)
    })

    const placeOrder = async () => {
      if (!hasSelectedItems.value || submitting.value) return

      const selectedItems = data.value.recommendations
        .filter(r => r.selected)
        .map(r => ({ sku: r.sku, name: r.name, quantity: r.restock_quantity, unit_cost: r.unit_cost }))
      const totalCost = data.value.total_selected_cost

      try {
        submitting.value = true
        await api.submitRestockingOrder({ items: selectedItems, total_cost: totalCost })
        successMessage.value = t('restocking.orderSuccess')
        setTimeout(() => { successMessage.value = '' }, 3000)
        await loadRecommendations()
      } catch (err) {
        error.value = 'Failed to submit restocking order: ' + err.message
      } finally {
        submitting.value = false
      }
    }

    onMounted(loadRecommendations)

    return {
      t,
      loading,
      error,
      data,
      budget,
      submitting,
      successMessage,
      hasSelectedItems,
      placeOrder
    }
  }
}
</script>

<style scoped>
.budget-slider {
  width: 100%;
  margin: 1rem 0;
  accent-color: #2563eb;
  height: 6px;
}

.budget-display {
  font-size: 1.5rem;
  font-weight: 700;
  color: #0f172a;
}

.row-selected {
  background: #f0fdf4;
}

.row-dimmed {
  opacity: 0.5;
}

.place-order-section {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-top: 1rem;
}

.btn-primary {
  background: #2563eb;
  color: white;
  border: none;
  padding: 0.75rem 1.5rem;
  border-radius: 8px;
  font-weight: 600;
  font-size: 0.938rem;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-primary:hover:not(:disabled) {
  background: #1d4ed8;
}

.btn-primary:disabled {
  background: #94a3b8;
  cursor: not-allowed;
}

.success-message {
  background: #d1fae5;
  color: #065f46;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  font-weight: 500;
}
</style>
