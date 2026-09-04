import { LightningElement } from 'lwc';
import getPendingApprovals from '@salesforce/apex/CheckoutController.getPendingApprovals';
import getApprovalHistory from '@salesforce/apex/CheckoutController.getApprovalHistory';
import resolveApproval from '@salesforce/apex/CheckoutController.resolveApproval';

export default class ManagerApproval extends LightningElement {
    pendingOrders = [];
    historyOrders = [];
    isLoading = false;
    isLoadingHistory = false;
    errorMessage = null;
    historyErrorMessage = null;
    actionMessage = null;

    connectedCallback() {
        this.loadPendingOrders();
        this.loadHistory();
    }

    async loadPendingOrders() {
        this.isLoading = true;
        this.errorMessage = null;
        try {
            const results = await getPendingApprovals();
            this.pendingOrders = results.map(o => ({
                ...o,
                formattedTotal: o.totalAmount != null ? o.totalAmount.toFixed(2) : '0.00'
            }));
        } catch (error) {
            this.errorMessage = (error && error.body && error.body.message)
                ? error.body.message
                : 'Failed to load pending approvals.';
        } finally {
            this.isLoading = false;
        }
    }

    async loadHistory() {
        this.isLoadingHistory = true;
        this.historyErrorMessage = null;
        try {
            const results = await getApprovalHistory();
            this.historyOrders = results.map(o => ({
                ...o,
                formattedTotal: o.totalAmount != null ? o.totalAmount.toFixed(2) : '0.00'
            }));
        } catch (error) {
            this.historyErrorMessage = (error && error.body && error.body.message)
                ? error.body.message
                : 'Failed to load approval history.';
        } finally {
            this.isLoadingHistory = false;
        }
    }

    get hasPendingOrders() {
        return this.pendingOrders && this.pendingOrders.length > 0;
    }

    get hasHistory() {
        return this.historyOrders && this.historyOrders.length > 0;
    }

    async handleApprove(event) {
        await this.resolveOrder(event.target.dataset.orderId, true);
    }

    async handleReject(event) {
        await this.resolveOrder(event.target.dataset.orderId, false);
    }

    async resolveOrder(orderId, approved) {
        this.actionMessage = null;
        try {
            const result = await resolveApproval({ orderId, approved });
            this.actionMessage = result.message;
            await this.loadPendingOrders();
            await this.loadHistory();
        } catch (error) {
            this.actionMessage = (error && error.body && error.body.message)
                ? error.body.message
                : 'Failed to update approval status.';
        }
    }
}