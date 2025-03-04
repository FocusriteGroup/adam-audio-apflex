import matplotlib.pyplot as plt
import numpy as np

# Generate data
x = np.linspace(0, 2 * np.pi, 100)
y = np.sin(x)

# Create the plot
plt.plot(x, y)

# Add title and labels
plt.title('Sine Wave')
plt.xlabel('x')
plt.ylabel('sin(x)')

# Show the plot
plt.show()