import { LightningElement, wire, api } from 'lwc';
import getProducts from '@salesforce/apex/ProductCatalogController.getProducts';

export default class ProductCatalog extends LightningElement {
    @api testAccountId = null;

    @wire(getProducts, { testAccountId: '$testAccountId' })
    products;

    handleAddToCart(event) {
        const { id, name, price } = event.target.dataset;
        this.dispatchEvent(new CustomEvent('addtocart', {
            detail: {
                productId: id,
                productName: name,
                unitPrice: parseFloat(price),
                quantity: 1
            },
            bubbles: true,
            composed: true
        }));
    }
}
