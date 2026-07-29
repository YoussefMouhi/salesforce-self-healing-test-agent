import { LightningElement, api } from 'lwc';

export default class CartSummary extends LightningElement {
    cartItems = [];

    @api
    addItem(productId, productName, unitPrice, quantity) {
        const existing = this.cartItems.find(item => item.productId === productId);
        if (existing) {
            existing.quantity += quantity;
        } else {
            this.cartItems = [
                ...this.cartItems,
                { productId, productName, unitPrice, quantity }
            ];
        }
        this.cartItems = [...this.cartItems];
    }

    @api
    updateQuantity(productId, newQuantity) {
        this.cartItems = this.cartItems.map(item =>
            item.productId === productId ? { ...item, quantity: newQuantity } : item
        );
    }

    @api
    removeItem(productId) {
        this.cartItems = this.cartItems.filter(item => item.productId !== productId);
    }

    @api
    get items() {
        return this.cartItems;
    }

    @api
    get cartTotal() {
        return this.total;
    }

    get total() {
        return this.cartItems.reduce((sum, item) => sum + item.unitPrice * item.quantity, 0);
    }

    handleQuantityChange(event) {
        const productId = event.target.dataset.id;
        const newQuantity = parseInt(event.target.value, 10);
        this.updateQuantity(productId, newQuantity);
        this.dispatchEvent(new CustomEvent('quantitychanged', { bubbles: true, composed: true }));
    }

    handleRemove(event) {
        const productId = event.target.dataset.id;
        this.removeItem(productId);
        this.dispatchEvent(new CustomEvent('itemremoved', { bubbles: true, composed: true }));
    }
}
