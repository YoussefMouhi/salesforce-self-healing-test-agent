import { LightningElement, track, api } from 'lwc';

export default class Storefront extends LightningElement {
    @api testAccountId = null;
    @track cartItems = [];

    handleAddToCart(event) {
        const cart = this.template.querySelector('c-cart-summary');
        const { productId, productName, unitPrice, quantity } = event.detail;
        cart.addItem(productId, productName, unitPrice, quantity);
        this.syncCartItems();
    }

    handleCartChanged() {
        this.syncCartItems();
    }

    syncCartItems() {
        const cart = this.template.querySelector('c-cart-summary');
        this.cartItems = cart ? cart.items : [];
    }

    handleOrderSubmitted(event) {
        const cart = this.template.querySelector('c-cart-summary');
        if (cart) {
            [...this.cartItems].forEach(item => cart.removeItem(item.productId));
        }
        this.syncCartItems();
    }
}
