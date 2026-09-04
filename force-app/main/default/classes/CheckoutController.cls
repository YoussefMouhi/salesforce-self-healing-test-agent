public with sharing class CheckoutController {

    public class CartLineInput {
        @AuraEnabled public Id productId;
        @AuraEnabled public Integer quantity;
    }

    public class CheckoutResult {
        @AuraEnabled public Id orderId;
        @AuraEnabled public Decimal totalAmount;
        @AuraEnabled public Boolean approvalRequired;
    }

    private static final Decimal APPROVAL_THRESHOLD = 10000;

    @AuraEnabled
    public static CheckoutResult submitOrder(String testAccountId, String linesJson) {
        List<CartLineInput> lines = (List<CartLineInput>) JSON.deserialize(linesJson, List<CartLineInput>.class);

        if (lines == null || lines.isEmpty()) {
            throw new AuraHandledException('Cart is empty.');
        }

        Id accountId = resolveAccountId(testAccountId);
        Id pricebookId = resolveAssignedPricebookId(accountId);

        Set<Id> productIds = new Set<Id>();
        for (CartLineInput line : lines) {
            productIds.add(line.productId);
        }

        Map<Id, PricebookEntry> entriesByProduct = new Map<Id, PricebookEntry>();
        for (PricebookEntry pbe : [
            SELECT Id, Product2Id, UnitPrice
            FROM PricebookEntry
            WHERE Pricebook2Id = :pricebookId
            AND Product2Id IN :productIds
            AND IsActive = true
        ]) {
            entriesByProduct.put(pbe.Product2Id, pbe);
        }

        Decimal total = 0;
        for (CartLineInput line : lines) {
            PricebookEntry pbe = entriesByProduct.get(line.productId);
            if (pbe == null) {
                throw new AuraHandledException('No active price found for product ' + line.productId + ' in the resolved price book.');
            }
            total += pbe.UnitPrice * line.quantity;
        }

        Boolean needsApproval = total > APPROVAL_THRESHOLD;

        Order ord = new Order(
            AccountId = accountId,
            Pricebook2Id = pricebookId,
            EffectiveDate = Date.today(),
            Status = 'Draft',
            Approval_Required__c = needsApproval
        );
        insert ord;

        List<OrderItem> orderItems = new List<OrderItem>();
        for (CartLineInput line : lines) {
            PricebookEntry pbe = entriesByProduct.get(line.productId);
            orderItems.add(new OrderItem(
                OrderId = ord.Id,
                PricebookEntryId = pbe.Id,
                Quantity = line.quantity,
                UnitPrice = pbe.UnitPrice
            ));
        }
        insert orderItems;

        CheckoutResult result = new CheckoutResult();
        result.orderId = ord.Id;
        result.totalAmount = total;
        result.approvalRequired = needsApproval;
        return result;
    }

    private static Id resolveAccountId(String testAccountId) {
        if (String.isNotBlank(testAccountId)) {
            return (Id) testAccountId;
        }
        return null;
    }

    private static Id resolveAssignedPricebookId(Id accountId) {
        String targetName = 'Standard Price Book';

        if (accountId != null) {
            Account acc = [SELECT Assigned_Price_Book__c FROM Account WHERE Id = :accountId LIMIT 1];
            if (String.isNotBlank(acc.Assigned_Price_Book__c)) {
                targetName = acc.Assigned_Price_Book__c;
            }
        }

        List<Pricebook2> books = [SELECT Id FROM Pricebook2 WHERE Name = :targetName LIMIT 1];
        if (books.isEmpty()) {
            throw new AuraHandledException('Price book not found: ' + targetName);
        }
        return books[0].Id;
    }

    public class ApprovalEmailResult {
        @AuraEnabled public Boolean success;
        @AuraEnabled public String message;
    }

    @AuraEnabled
    public static ApprovalEmailResult sendApprovalEmail(Id orderId) {
        ApprovalEmailResult result = new ApprovalEmailResult();
        try {
            Order ord = [
                SELECT Id, TotalAmount, Account.Name, Account.Owner.Email
                FROM Order
                WHERE Id = :orderId
                LIMIT 1
            ];

            String toAddress = ord.Account.Owner.Email;
            if (String.isBlank(toAddress)) {
                throw new AuraHandledException('No approver email found for this account owner.');
            }

            String amountStr = ord.TotalAmount == null ? '0.00' : ord.TotalAmount.setScale(2).format();

            Messaging.SingleEmailMessage mail = new Messaging.SingleEmailMessage();
            mail.setToAddresses(new String[] { toAddress });
            mail.setSubject('Approval needed -- Order ' + ord.Id);
            mail.setPlainTextBody(
                'An order totaling $' + amountStr + ' has been submitted and requires your approval.\n\n' +
                'Account: ' + ord.Account.Name + '\n' +
                'Order ID: ' + ord.Id + '\n' +
                'Total: $' + amountStr + '\n\n' +
                'Please review and approve or reject this order.'
            );
            Messaging.sendEmail(new Messaging.SingleEmailMessage[] { mail });

            ord.Approval_Status__c = 'Pending';
            update ord;

            result.success = true;
            result.message = 'Approval email sent to ' + toAddress;
        } catch (Exception e) {
            result.success = false;
            result.message = e.getMessage();
        }
        return result;
    }

    public class PendingApprovalInfo {
        @AuraEnabled public Id orderId;
        @AuraEnabled public String accountName;
        @AuraEnabled public Decimal totalAmount;
        @AuraEnabled public Datetime createdDate;
    }

    @AuraEnabled
    public static List<PendingApprovalInfo> getPendingApprovals() {
        List<PendingApprovalInfo> results = new List<PendingApprovalInfo>();

        for (Order ord : [
            SELECT Id, TotalAmount, CreatedDate, Account.Name
            FROM Order
            WHERE Approval_Status__c = 'Pending'
            ORDER BY CreatedDate DESC
        ]) {
            PendingApprovalInfo info = new PendingApprovalInfo();
            info.orderId = ord.Id;
            info.accountName = ord.Account.Name;
            info.totalAmount = ord.TotalAmount;
            info.createdDate = ord.CreatedDate;
            results.add(info);
        }

        return results;
    }

    public class ApprovalHistoryInfo {
        @AuraEnabled public Id orderId;
        @AuraEnabled public String accountName;
        @AuraEnabled public Decimal totalAmount;
        @AuraEnabled public Datetime createdDate;
        @AuraEnabled public String approvalStatus;
    }

    @AuraEnabled
    public static List<ApprovalHistoryInfo> getApprovalHistory() {
        List<ApprovalHistoryInfo> results = new List<ApprovalHistoryInfo>();

        for (Order ord : [
            SELECT Id, TotalAmount, CreatedDate, Account.Name, Approval_Status__c
            FROM Order
            WHERE Approval_Status__c IN ('Approved', 'Rejected')
            ORDER BY CreatedDate DESC
            LIMIT 50
        ]) {
            ApprovalHistoryInfo info = new ApprovalHistoryInfo();
            info.orderId = ord.Id;
            info.accountName = ord.Account.Name;
            info.totalAmount = ord.TotalAmount;
            info.createdDate = ord.CreatedDate;
            info.approvalStatus = ord.Approval_Status__c;
            results.add(info);
        }

        return results;
    }

    @AuraEnabled
    public static ApprovalEmailResult resolveApproval(Id orderId, Boolean approved) {
        ApprovalEmailResult result = new ApprovalEmailResult();
        try {
            Order ord = new Order(
                Id = orderId,
                Approval_Status__c = approved ? 'Approved' : 'Rejected'
            );
            update ord;

            result.success = true;
            result.message = approved ? 'Order approved.' : 'Order rejected.';
        } catch (Exception e) {
            result.success = false;
            result.message = e.getMessage();
        }
        return result;
    }
}
