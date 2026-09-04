import { LightningElement, api } from 'lwc';
import submitOrder from '@salesforce/apex/CheckoutController.submitOrder';
import sendApprovalEmail from '@salesforce/apex/CheckoutController.sendApprovalEmail';

const APPROVAL_THRESHOLD = 10000;

export default class CheckoutForm extends LightningElement {
    @api testAccountId = null;
    @api cartItems = [];

    isSubmitting = false;
    orderId = null;
    errorMessage = null;

    approvalRequired = false;
    approvalStatus = null; // 'draft' | 'pending' | 'approved' | 'rejected'
    approvalMessage = null;
    isSendingApproval = false;
    submittedTotal = 0;

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

    get showApprovalSection() {
        return this.approvalRequired;
    }

    get isDraftStatus() {
        return this.approvalStatus === 'draft';
    }

    get isPendingStatus() {
        return this.approvalStatus === 'pending';
    }

    get isApprovedStatus() {
        return this.approvalStatus === 'approved';
    }

    get isRejectedStatus() {
        return this.approvalStatus === 'rejected';
    }

    get approvalEmailPreview() {
        const amount = this.submittedTotal.toFixed(2);
        return `Subject: Approval needed -- Order ${this.orderId}

` +
            `An order totaling $${amount} has been submitted and requires your approval.

` +
            `Order ID: ${this.orderId}
` +
            `Total: $${amount}

` +
            `Please review and approve or reject this order.`;
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
            this.submittedTotal = result.totalAmount;
            this.approvalRequired = result.approvalRequired;
            this.approvalStatus = result.approvalRequired ? 'draft' : null;
            this.approvalMessage = null;

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

    async handleSendApproval() {
        this.isSendingApproval = true;
        try {
            const result = await sendApprovalEmail({ orderId: this.orderId });
            this.approvalMessage = result.message;
            if (result.success) {
                this.approvalStatus = 'pending';
            }
        } catch (error) {
            this.approvalMessage = (error && error.body && error.body.message)
                ? error.body.message
                : 'Failed to send approval email.';
        } finally {
            this.isSendingApproval = false;
        }
    }

}
