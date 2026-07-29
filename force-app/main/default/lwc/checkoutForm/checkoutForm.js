import { LightningElement, api } from 'lwc';
import submitOrder from '@salesforce/apex/CheckoutController.submitOrder';

const APPROVAL_THRESHOLD = 10000;

export default class CheckoutForm extends LightningElement {
    @api testAccountId = null;
    @api cartItems = [];

    isSubmitting = false;
    orderId = null;
    errorMessage = null;

    get debugCartItemsJson() {
        return JSON.stringify(this.cartItems);
    }

    get hasItems() {
        return this.cartItems && this.cartItems.length > 0;
    }

    get total() {
        return this.cartItems.reduce((sum, item) => sum + item.unitPrice * item.quantity, 0);
    }

    get willRequireApproval() {
        return this.total > APPROVAL_THRESHOLD;
    }

    get submitDisabled() {
        return !this.hasItems || this.isSubmitting;
    }

    async handleSubmit() {
        this.errorMessage = null;
        this.isSubmitting = true;

        const lines = this.cartItems.map(item => ({
            productId: item.productId,
            quantity: item.quantity
        }));

        try {
            const result = await submitOrder({
                testAccountId: this.testAccountId,
                linesJson: JSON.stringify(lines)
            });
            this.orderId = result.orderId;

            this.dispatchEvent(new CustomEvent('ordersubmitted', {
                detail: {
                    orderId: result.orderId,
                    totalAmount: result.totalAmount,
                    approvalRequired: result.approvalRequired
                },
                bubbles: true,
                composed: true
            }));
        } catch (error) {
            this.errorMessage = (error && error.body && error.body.message)
                ? error.body.message
                : 'Checkout failed. Please try again.';
        } finally {
            this.isSubmitting = false;
        }
    }
}
