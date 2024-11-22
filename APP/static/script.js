
async function fetchClassMapping() {
    try {
        const response = await fetch('/api/class_mapping'); // Ensure this endpoint exists on the backend
        if (!response.ok) {
            throw new Error('Failed to fetch class mapping');
        }
        const classMapping = await response.json();
        console.log('Class Mapping:', classMapping); // You can use this mapping in your code
        return classMapping;
    } catch (error) {
        console.error('Error fetching class mapping:', error);
    }
}


document.addEventListener('DOMContentLoaded', async () => {
    const processedImage = document.getElementById('processedImage');
    const predictionDetails = document.getElementById('predictionDetails');
    const productCountDetails = document.getElementById('productCountDetails');
    const timerElement = document.getElementById('timer');
    const productLivenessDiv = document.getElementById('productLiveness');
    
    let timeRemaining = 16; // Total time for the interval
    let countdownInterval;  // For controlling the countdown interval
    const productCounts = new Map(); // Store product counts
    const fruitCounts = new Map(); // Store fruit/vegetable counts
    const classMapping = await fetchClassMapping(); // Fetch class mapping

    async function checkForDetection() {
        try {
            const response = await fetch('/get_latest_capture');
            if (!response.ok) {
                console.error('Failed to fetch the latest capture.');
                return;
            }

            const data = await response.json();
            console.log('Received data:', data); // Log the received data for debugging

            if (data.image_url) {
                processedImage.src = data.image_url;
                processedImage.style.display = 'block';

                // Clear previous predictions
                predictionDetails.innerHTML = '';

                if (data.detections && data.detections.length > 0) {
                    const seenProducts = new Set(); // Track seen products in this cycle

                    // Loop through detections
                    for (const det of data.detections) {
                        predictionDetails.innerHTML += `<p>Class: ${det.class}, Confidence: ${det.confidence.toFixed(2)}</p>`;

                        // Check if the class is valid before fetching liveness
                        if (det.class && classMapping.hasOwnProperty(det.class)) {
                            fetchProductLiveness(det.class);
                        } else {
                            console.error('Invalid class detected:', det.class);
                        }

                        // Fetch product details for the detected class
                        const productResponse = await fetch(`/get_product_details/${det.class}`);
                        if (productResponse.ok) {
                            const productData = await productResponse.json();

                            // Increment the product count
                            if (!seenProducts.has(productData.product_name)) {
                                // Check if the product already exists in the map
                                if (productCounts.has(productData.product_name)) {
                                    const productInfo = productCounts.get(productData.product_name);
                                    productCounts.set(productData.product_name, { count: productInfo.count + 1, brand: productData.brand });
                                } else {
                                    // If it doesn't exist, add it with count = 1 and store the brand
                                    productCounts.set(productData.product_name, { count: 1, brand: productData.brand });
                                    displayProductDetails(productData);
                                }

                                seenProducts.add(productData.product_name); // Add to seen products
                            }
                        } else {
                            console.error('Failed to fetch product details for:', det.class);
                        }

                        // Increment fruit and vegetable count
                        if (det.class && classMapping[det.class]) {
                            const fruitOrVeg = classMapping[det.class];
                            if (fruitCounts.has(fruitOrVeg)) {
                                const currentCount = fruitCounts.get(fruitOrVeg);
                                fruitCounts.set(fruitOrVeg, currentCount + 1);
                            } else {
                                fruitCounts.set(fruitOrVeg, 1);
                            }
                        }
                    }

                    // Update the product count display
                    updateProductCount();
                    updateFruitCount(); // Update fruit/vegetable counts
                } else {
                    console.log('No detections found in this image.');
                    productCountDetails.innerHTML = '<p>No products detected.</p>'; // Clear or update product count display
                }
            }
        } catch (error) {
            console.error('Error during detection:', error);
        }
    }

    function displayProductDetails(productData) {
        const productDetails = document.getElementById('productDetails');
        if (productData && productData.product_id) {
            // Check if the product is already displayed
            if (!document.getElementById(`product-${productData.product_id}`)) {
                productDetails.innerHTML += `
                    <div id="product-${productData.product_id}">
                        <h4>${productData.product_name} (${productData.brand})</h4>
                        <p>Product ID: ${productData.product_id}</p>
                        <p>Manufactured Date: ${productData.mfg_date}</p>
                        <p>Use Before: ${productData.use_before}</p>
                        <p>MRP: ${productData.mrp}</p>
                        <p>Net Weight: ${productData.net_weight}</p>
                    </div>
                `;
            }
        } else {
            console.error('Invalid product data:', productData);
        }
    }

    function updateProductCount() {
        productCountDetails.innerHTML = ''; // Clear existing count display

        // Display the updated count for each product
        productCounts.forEach((value, name) => {
            const count = value.count;
            const brand = value.brand;
            if (count > 0) {
                productCountDetails.innerHTML += `<p>${name} (${brand}): ${count}</p>`;
            }
        });
    }

    function updateFruitCount() {
        const fruitCountDetails = document.getElementById('fruitCountDetails'); // Ensure this element exists
        if (fruitCountDetails) {
            fruitCountDetails.innerHTML = ''; // Clear existing count display

            // Display the updated count for each fruit/vegetable
            fruitCounts.forEach((count, name) => {
                if (count > 0) {
                    fruitCountDetails.innerHTML += `<p>${name}: ${count}</p>`;
                }
            });
        } else {
            console.error('fruitCountDetails element not found.');
        }
    }

    function startCountdown() {
        clearInterval(countdownInterval); // Clear any existing interval to avoid multiple timers
        timeRemaining = 16; // Reset the timer

        countdownInterval = setInterval(() => {
            if (timeRemaining > 0) {
                timeRemaining--;
                timerElement.textContent = timeRemaining;
            } else {
                timeRemaining = 16;  // Reset the timer once it reaches 0
                timerElement.textContent = timeRemaining;
                checkForDetection(); // Trigger detection when timer resets
            }
        }, 1000);
    }

    // Function to fetch and display the product liveness
    async function fetchProductLiveness(detectedClass) {
        try {
            // Fetch the liveness from the backend
            const response = await fetch(`/get_product_liveness/${detectedClass}`);
            const data = await response.json();

            // Display the liveness in the front end
            productLivenessDiv.innerHTML = `Liveness: ${data.liveness}`;
        } catch (error) {
            console.error("Error fetching product liveness:", error);
        }
    }

    checkForDetection(); // Initial detection check
    startCountdown(); // Start countdown on page load
});
